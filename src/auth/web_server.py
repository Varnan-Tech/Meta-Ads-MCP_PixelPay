"""
FastAPI web server for OAuth endpoints, webhooks, and admin routes.
This runs separately from the MCP server to handle HTTP requests.
"""
import html
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import requests
from pydantic import BaseModel
from fastapi import Body

try:
    from ..config.settings import settings
    from ..utils.logger import logger
    from .database import init_database, get_db_session, FacebookToken, OAuthState
    from .oauth_service import oauth_service
    from .web_server_token_endpoint import router as token_router
    from ..auth.token_manager import token_manager
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from config.settings import settings
    from utils.logger import logger
    from auth.database import init_database, get_db_session, FacebookToken, OAuthState
    from auth.oauth_service import oauth_service
    from auth.web_server_token_endpoint import router as token_router
    from auth.token_manager import token_manager

# Initialize FastAPI app
app = FastAPI(
    title="Meta Ads MCP OAuth Server",
    description="OAuth endpoints for Facebook Login integration",
    version="1.0.0"
)

# CORS middleware (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include token processing router (implicit flow callback handler)
app.include_router(token_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database and start background workers on startup."""
    init_database()
    
    # Start token refresh worker
    try:
        from .token_refresh_worker import start_refresh_worker
        start_refresh_worker()
        logger.info("Token refresh worker started")
    except Exception as e:
        logger.warning(f"Failed to start token refresh worker: {e}")
    
    logger.info("OAuth web server started")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background workers on shutdown."""
    try:
        from .token_refresh_worker import stop_refresh_worker
        stop_refresh_worker()
        logger.info("Token refresh worker stopped")
    except Exception as e:
        logger.warning(f"Error stopping token refresh worker: {e}")


# Mount static files (if static directory exists)
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/")
async def root():
    """Root endpoint - show login page."""
    login_page = static_path / "login.html"
    if login_page.exists():
        return FileResponse(login_page)
    return HTMLResponse("""
    <html>
        <head><title>Meta Ads MCP OAuth</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>Meta Ads MCP OAuth Server</h1>
            <p>Status: Running</p>

            <div style="margin: 20px auto; max-width: 520px; text-align: left; background:#f8fafc; padding:16px; border-radius:10px;">
                <label style="display:block; font-weight:600; margin-bottom:8px;">Connection method</label>
                <div style="display:flex; gap:16px; align-items:center;">
                    <label><input type="radio" name="conn" value="oauth" checked> Use OAuth (recommended)</label>
                    <label><input type="radio" name="conn" value="manual"> Use manual access token</label>
                </div>
            </div>

            <div id="oauthBlock">
                <p><a href="/auth/facebook" style="background: #1877f2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Connect Facebook</a></p>
            </div>

            <div id="manualBlock" style="display:none; max-width:520px; margin:0 auto; text-align:left;">
                <form id="manualForm" onsubmit="return false;" style="background:#f8fafc; padding:16px; border-radius:10px;">
                    <label style="display:block; font-weight:600; margin-bottom:6px;">Access Token</label>
                    <input id="tokenInput" type="password" placeholder="EAA..." style="width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:8px;">
                    <div style="display:flex; gap:8px; margin-top:12px;">
                        <button id="saveTokenBtn" style="background:#0ea5e9; color:white; border:none; padding:10px 16px; border-radius:8px; cursor:pointer;">Save Token</button>
                        <span id="manualMsg" style="line-height:32px; color:#475569;"></span>
                    </div>
                </form>
            </div>

            <p style="margin-top:24px;">
                <a href="/admin/facebook/connections" style="margin-right:10px;">View Connections</a> | 
                <a href="/logout" style="color:#dc2626;">Logout & Revoke Access</a>
            </p>

            <script>
                const radios = document.getElementsByName('conn');
                const oauthBlock = document.getElementById('oauthBlock');
                const manualBlock = document.getElementById('manualBlock');
                const saveBtn = document.getElementById('saveTokenBtn');
                const tokenInput = document.getElementById('tokenInput');
                const msg = document.getElementById('manualMsg');

                radios.forEach(r => r.addEventListener('change', () => {
                    const mode = Array.from(radios).find(x => x.checked).value;
                    oauthBlock.style.display = mode === 'oauth' ? 'block' : 'none';
                    manualBlock.style.display = mode === 'manual' ? 'block' : 'none';
                }));

                saveBtn.addEventListener('click', async () => {
                    msg.textContent = 'Saving...';
                    try {
                        const res = await fetch('/admin/manual-token', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ token: tokenInput.value })
                        });
                        const data = await res.json();
                        if (data.success) {
                            msg.textContent = 'Saved. Token is now active for this server.';
                        } else {
                            msg.textContent = 'Error: ' + (data.error || 'Failed to save token');
                        }
                    } catch (e) {
                        msg.textContent = 'Error: ' + e;
                    }
                });
            </script>
        </body>
    </html>
    """)


@app.get("/login")
async def login_page():
    """Login page endpoint."""
    login_page = static_path / "login.html"
    if login_page.exists():
        return FileResponse(login_page)
    return RedirectResponse(url="/")


@app.get("/auth/facebook/success")
async def auth_success():
    """Display success page after authentication."""
    # Get the most recent connection
    db = get_db_session()
    accounts_html = ""
    try:
        latest_token = db.query(FacebookToken).order_by(FacebookToken.created_at.desc()).first()

        if latest_token:
            logger.info(f"Loading accounts for token {latest_token.fb_user_id}, accounts field type: {type(latest_token.accounts)}")
            logger.info(f"Accounts data: {latest_token.accounts}")

            if latest_token.accounts:
                import json
                # Handle both string JSON and direct list
                if isinstance(latest_token.accounts, str):
                    try:
                        accounts = json.loads(latest_token.accounts)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse accounts JSON: {e}")
                        accounts = []
                elif isinstance(latest_token.accounts, list):
                    accounts = latest_token.accounts
                else:
                    logger.error(f"Unexpected accounts type: {type(latest_token.accounts)}")
                    accounts = []

                logger.info(f"Parsed {len(accounts)} accounts")

                if accounts:
                    accounts_html = "<div style='margin-top: 20px;'>"
                    for account in accounts:
                        account_name = html.escape(str(account.get('name', 'Unknown')))
                        account_id = html.escape(str(account.get('id', 'N/A')))
                        account_status = str(account.get('account_status', account.get('status', 'Unknown')))
                        accounts_html += f"""
                        <div style='background: #f0f4f8; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #667eea;'>
                            <strong>{account_name}</strong><br>
                            <small>ID: {account_id}</small><br>
                            <small>Status: {account_status}</small>
                        </div>
                        """
                    accounts_html += "</div>"
            else:
                logger.warning("No accounts data found in token record")
        else:
            logger.warning("No token record found")
    except Exception as e:
        logger.error(f"Error loading accounts: {e}", exc_info=True)
    finally:
        db.close()
    
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Success - Connected!</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }}
                .container {{
                    background: white;
                    border-radius: 20px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                    padding: 40px;
                    max-width: 500px;
                    width: 100%;
                    text-align: center;
                }}
                .success-icon {{
                    width: 80px;
                    height: 80px;
                    background: #4caf50;
                    border-radius: 50%;
                    margin: 0 auto 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 40px;
                    color: white;
                }}
                h1 {{ color: #333; margin-bottom: 10px; }}
                .subtitle {{ color: #666; margin-bottom: 30px; }}
                .button {{
                    display: inline-block;
                    padding: 12px 24px;
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 8px;
                    margin: 10px;
                    font-weight: 600;
                    transition: all 0.3s ease;
                }}
                .button:hover {{ background: #5568d3; transform: translateY(-2px); }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✓</div>
                <h1>Successfully Connected!</h1>
                <p class="subtitle">Your Facebook account has been connected to Meta Ads MCP</p>
                
                <h2 style="color: #333; margin-top: 30px; margin-bottom: 15px; font-size: 18px;">Connected Ad Accounts:</h2>
                {accounts_html if accounts_html else "<p style='color: #999;'>No ad accounts found. Make sure your account has access to ad accounts.</p>"}
                
                <div style="margin-top: 30px;">
                    <a href="/admin/facebook/connections" class="button">View All Connections</a>
                    <a href="/" class="button" style="background: #1877f2;">Back to Home</a>
                    <a href="/logout" class="button" style="background: #dc2626;">Logout & Revoke Access</a>
                </div>
            </div>
        </body>
        </html>
        """
    )


@app.get("/auth/facebook")
async def auth_facebook(user_id: Optional[str] = Query(None)):
    """
    Initiate Facebook OAuth flow.
    
    Query params:
        user_id: Optional app user ID
    """
    if not settings.is_oauth_configured:
        raise HTTPException(
            status_code=503,
            detail="OAuth is not configured. Please set FB_APP_ID, FB_APP_SECRET, and FB_REDIRECT_URI."
        )
    
    try:
        # Generate state token
        state = oauth_service.generate_state(user_id=user_id)
        
        # Get authorization URL
        auth_url = oauth_service.get_authorization_url(state)
        
        # Redirect to Facebook
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Failed to initiate OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/facebook/callback")
async def auth_facebook_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_reason: Optional[str] = Query(None)
):
    """
    Handle Facebook OAuth callback.
    
    For implicit flow (response_type=token), serve callback.html which uses JavaScript
    to extract the token from the URL fragment and POST it to /auth/facebook/callback/token.
    
    For authorization code flow (response_type=code), process the code directly.
    """
    # If there's a fragment (implicit flow), serve the callback page
    # The JavaScript will extract the token and POST it to /callback/token
    if '#' in str(request.url) or not code:
        # Serve callback.html which handles fragment extraction client-side
        callback_page = static_path / "callback.html"
        if callback_page.exists():
            return FileResponse(callback_page)
        else:
            # Fallback: redirect to success page
            return HTMLResponse("""
            <html>
                <head><title>Processing...</title></head>
                <body>
                    <h1>Processing Authentication...</h1>
                    <p>If you see this, the callback page is missing. Please check the implementation.</p>
                    <script>
                        // Extract token from fragment
                        const fragment = window.location.hash.substring(1);
                        const params = {};
                        fragment.split('&').forEach(param => {
                            const [key, value] = param.split('=');
                            if (key && value) params[key] = decodeURIComponent(value);
                        });
                        
                        if (params.access_token) {
                            // POST token to server
                            fetch('/auth/facebook/callback/token', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({
                                    access_token: params.access_token,
                                    expires_in: parseInt(params.expires_in || '0'),
                                    token_type: params.token_type || 'bearer',
                                    state: params.state
                                })
                            }).then(() => {
                                window.location.href = '/auth/facebook/success';
                            });
                        }
                    </script>
                </body>
            </html>
            """)
    
    # Continue with authorization code flow (original implementation)
    if error:
        error_msg = f"OAuth error: {error}"
        if error_reason:
            error_msg += f" ({error_reason})"
        logger.warning(error_msg)
        return HTMLResponse(
            content=f"""
            <html>
                <body>
                    <h1>Authentication Failed</h1>
                    <p>{html.escape(error_msg)}</p>
                    <p><a href="/auth/facebook">Try again</a></p>
                </body>
            </html>
            """,
            status_code=400
        )
    
    if not code or not state:
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Invalid Request</title>
                <style>
                    body { font-family: Arial; text-align: center; padding: 50px; }
                    .button { display: inline-block; padding: 10px 20px; background: #1877f2; color: white; text-decoration: none; border-radius: 5px; margin: 10px; }
                </style>
            </head>
            <body>
                <h1>Invalid Request</h1>
                <p>Missing code or state parameter.</p>
                <a href="/auth/facebook" class="button">Try Again</a>
            </body>
            </html>
            """,
            status_code=400
        )
    
    try:
        # Validate state
        user_id = oauth_service.validate_state(state)
        if user_id is None:
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Session Expired</title>
                    <style>
                        body { font-family: Arial; text-align: center; padding: 50px; }
                        .button { display: inline-block; padding: 10px 20px; background: #1877f2; color: white; text-decoration: none; border-radius: 5px; margin: 10px; }
                    </style>
                </head>
                <body>
                    <h1>Invalid or Expired Session</h1>
                    <p>The authentication session has expired. Please try again.</p>
                    <a href="/auth/facebook" class="button">Try Again</a>
                </body>
                </html>
                """,
                status_code=400
            )
        
        # Exchange code for short token
        short_token_response = oauth_service.exchange_code_for_token(code)
        short_token = short_token_response.get("access_token")
        
        # Exchange short token for long token
        long_token_response = oauth_service.exchange_short_token_for_long(short_token)
        long_token = long_token_response.get("access_token")
        expires_in = long_token_response.get("expires_in", 5184000)
        
        # Get user info
        user_info = oauth_service.get_user_info(long_token)
        fb_user_id = user_info.get("id")
        
        # Get ad accounts (may fail if token doesn't have ads_read permission)
        accounts = []
        try:
            accounts = oauth_service.get_ad_accounts(long_token)
        except Exception as e:
            logger.warning(f"Could not fetch ad accounts (may need ads_read permission): {e}")
            # Continue without accounts - token is still valid for basic operations
        
        # Save token
        # Parse permissions from requested scopes
        permissions = settings.fb_oauth_scopes.split(",") if settings.fb_oauth_scopes else []
        oauth_service.save_token(
            user_id=user_id,
            fb_user_id=fb_user_id,
            access_token=long_token,
            expires_in=expires_in,
            permissions=permissions,
            accounts=accounts
        )
        
        # Success page with nice styling
        accounts_html = ""
        if accounts:
            accounts_html = "<div style='margin-top: 20px;'>"
            for account in accounts:
                account_name = html.escape(account.get('name', 'Unknown'))
                account_id = html.escape(account.get('id', 'N/A'))
                account_status = account.get('status', 'Unknown')
                accounts_html += f"""
                <div style='background: #f0f4f8; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #667eea;'>
                    <strong>{account_name}</strong><br>
                    <small>ID: {account_id}</small><br>
                    <small>Status: {account_status}</small>
                </div>
                """
            accounts_html += "</div>"
        
        # Redirect to success page
        return RedirectResponse(url="/auth/facebook/success")
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Authentication Error</title>
                <style>
                    body {{ font-family: Arial; text-align: center; padding: 50px; }}
                    .error {{ color: #c33; background: #fee; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    .button {{ display: inline-block; padding: 10px 20px; background: #1877f2; color: white; text-decoration: none; border-radius: 5px; margin: 10px; }}
                </style>
            </head>
            <body>
                <h1>Authentication Error</h1>
                <div class="error">{html.escape(str(e))}</div>
                <a href="/auth/facebook" class="button">Try Again</a>
                <a href="/" class="button" style="background: #667eea;">Back to Home</a>
            </body>
            </html>
            """,
            status_code=500
        )


@app.post("/webhooks/facebook/deauth")
async def webhook_deauth(request: Request):
    """
    Handle Facebook deauthorization webhook.
    Expects signed_request in form data.
    """
    try:
        form_data = await request.form()
        signed_request = form_data.get("signed_request")
        
        if not signed_request:
            raise HTTPException(status_code=400, detail="Missing signed_request")
        
        # Decode and verify signed_request
        # Format: <signature>.<payload> (both base64url encoded)
        import base64
        import hmac
        import hashlib
        import json
        
        parts = signed_request.split(".")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid signed_request format")
        
        # Decode payload
        payload_encoded = parts[1]
        # Add padding if needed
        padding = len(payload_encoded) % 4
        if padding:
            payload_encoded += '=' * (4 - padding)
        
        try:
            payload_data = base64.urlsafe_b64decode(payload_encoded)
            payload = json.loads(payload_data)
        except Exception as e:
            logger.error(f"Failed to decode signed_request payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload encoding")
        
        # Verify signature
        # Facebook uses HMAC-SHA256 with app_secret as key and payload as message
        expected_sig = hmac.new(
            settings.fb_app_secret.encode(),
            parts[1].encode(),
            hashlib.sha256
        ).digest()
        
        # Decode actual signature
        sig_encoded = parts[0]
        padding = len(sig_encoded) % 4
        if padding:
            sig_encoded += '=' * (4 - padding)
        
        try:
            actual_sig = base64.urlsafe_b64decode(sig_encoded)
        except Exception as e:
            logger.error(f"Failed to decode signature: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature encoding")
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            logger.warning("Invalid deauth webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Extract user ID
        user_id = payload.get("user_id")
        if not user_id:
            logger.warning("Deauth webhook missing user_id")
            return JSONResponse({"status": "ok"})  # Still return 200
        
        # Revoke token
        oauth_service.revoke_token(str(user_id))
        logger.info(f"Revoked token for FB user: {user_id}")
        
        return JSONResponse({"status": "ok"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deauth webhook error: {e}")
        # Still return 200 to prevent FB retries
        return JSONResponse({"status": "error", "message": str(e)})


class ManualTokenRequest(BaseModel):
    token: str


@app.post("/admin/manual-token")
async def set_manual_token(payload: ManualTokenRequest):
    """Store a manual access token via the file-based token manager."""
    try:
        if not payload.token or len(payload.token) < 50:
            raise HTTPException(status_code=400, detail="Invalid token")
        token_manager.set_token(payload.token, account_id="default")
        return JSONResponse({"success": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to store manual token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class LogoutRequest(BaseModel):
    user_id: Optional[str] = None
    fb_user_id: Optional[str] = None


@app.post("/admin/facebook/logout")
async def admin_logout(payload: LogoutRequest):
    """Revoke stored token(s) for the specified user_id or fb_user_id."""
    db = get_db_session()
    try:
        if not payload.user_id and not payload.fb_user_id:
            raise HTTPException(status_code=400, detail="Provide user_id or fb_user_id")

        query = db.query(FacebookToken)
        if payload.fb_user_id:
            query = query.filter(FacebookToken.fb_user_id == payload.fb_user_id)
        elif payload.user_id:
            query = query.filter(FacebookToken.user_id == payload.user_id)

        tokens = query.all()
        if not tokens:
            return JSONResponse({"success": True, "revoked": 0})

        revoked = 0
        for t in tokens:
            t.revoked = True
            revoked += 1
        db.commit()
        logger.info(f"Revoked {revoked} token(s) for logout request")
        return JSONResponse({"success": True, "revoked": revoked})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Logout failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/admin/facebook/refresh-accounts")
async def admin_refresh_accounts(user_id: Optional[str] = Query(None), fb_user_id: Optional[str] = Query(None)):
    """Refetch ad accounts using the stored OAuth token and update DB."""
    if not user_id and not fb_user_id:
        raise HTTPException(status_code=400, detail="Provide user_id or fb_user_id")

    # Resolve access token
    access_token = None
    try:
        if fb_user_id:
            access_token = oauth_service.get_token(fb_user_id=fb_user_id)
        elif user_id:
            access_token = oauth_service.get_token(user_id=user_id)
    except Exception as e:
        logger.error(f"Token lookup failed: {e}")

    if not access_token:
        raise HTTPException(status_code=404, detail="No active token found for specified user")

    # Fetch accounts from Meta and update DB record
    db = get_db_session()
    try:
        accounts = oauth_service.get_ad_accounts(access_token) or []

        query = db.query(FacebookToken).filter(FacebookToken.revoked == False)
        if fb_user_id:
            query = query.filter(FacebookToken.fb_user_id == fb_user_id)
        elif user_id:
            query = query.filter(FacebookToken.user_id == user_id)

        token_record = query.first()
        if not token_record:
            raise HTTPException(status_code=404, detail="Token record not found")

        token_record.accounts = accounts
        token_record.updated_at = datetime.now(timezone.utc)
        db.commit()

        return JSONResponse({
            "success": True,
            "accounts_count": len(accounts),
            "accounts": accounts
        })
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to refresh accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/admin/facebook/connections")
async def admin_connections(user_id: Optional[str] = Query(None)):
    """
    List Facebook connection status with revoke capability.
    
    Query params:
        user_id: Optional filter by app user ID
    """
    db = get_db_session()
    try:
        query = db.query(FacebookToken)
        if user_id:
            query = query.filter(FacebookToken.user_id == user_id)
        
        tokens = query.all()
        
        # Build HTML response
        connections_html = ""
        active_count = 0
        
        for token in tokens:
            status_color = "#10b981" if not token.revoked else "#ef4444"
            status_text = "Active" if not token.revoked else "Revoked"
            
            if not token.revoked:
                active_count += 1
            
            accounts_list = ""
            if token.accounts:
                for acc in token.accounts:
                    accounts_list += f"<li>{acc.get('name', 'Unknown')} ({acc.get('id', 'N/A')})</li>"
            
            revoke_button = ""
            if not token.revoked:
                revoke_button = f"""
                <button onclick="revokeConnection('{token.fb_user_id}')" 
                        style="background:#dc2626; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-size:12px; margin-top:10px;">
                    Revoke Access
                </button>
                """
            
            connections_html += f"""
            <div style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:8px; padding:20px; margin:15px 0;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                    <h3 style="margin:0; color:#111827;">Connection #{token.id[:8]}</h3>
                    <span style="background:{status_color}; color:white; padding:4px 12px; border-radius:12px; font-size:12px; font-weight:600;">
                        {status_text}
                    </span>
                </div>
                <div style="color:#6b7280; font-size:14px;">
                    <p><strong>FB User ID:</strong> {token.fb_user_id}</p>
                    <p><strong>Created:</strong> {token.created_at.strftime('%Y-%m-%d %H:%M:%S') if token.created_at else 'N/A'}</p>
                    <p><strong>Expires:</strong> {token.expires_at.strftime('%Y-%m-%d %H:%M:%S') if token.expires_at else 'N/A'}</p>
                    <p><strong>Ad Accounts:</strong> {len(token.accounts) if token.accounts else 0}</p>
                    {f"<ul style='margin:10px 0; padding-left:20px;'>{accounts_list}</ul>" if accounts_list else ""}
                </div>
                {revoke_button}
            </div>
            """
        
        return HTMLResponse(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Facebook Connections</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: #f3f4f6;
                        min-height: 100vh;
                        padding: 40px 20px;
                    }}
                    .container {{
                        max-width: 800px;
                        margin: 0 auto;
                        background: white;
                        border-radius: 12px;
                        padding: 40px;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    }}
                    h1 {{ color: #111827; margin-bottom: 10px; }}
                    .stats {{
                        background: #dbeafe;
                        padding: 15px;
                        border-radius: 8px;
                        margin: 20px 0;
                        color: #1e40af;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 10px 20px;
                        background: #667eea;
                        color: white;
                        text-decoration: none;
                        border-radius: 8px;
                        margin: 10px 5px 10px 0;
                        font-weight: 600;
                        transition: all 0.2s;
                    }}
                    .button:hover {{ background: #5568d3; }}
                    .button-danger {{ background: #dc2626; }}
                    .button-danger:hover {{ background: #b91c1c; }}
                    #message {{
                        padding: 15px;
                        border-radius: 8px;
                        margin: 20px 0;
                        display: none;
                    }}
                    .success {{ background: #d1fae5; color: #065f46; }}
                    .error {{ background: #fee2e2; color: #991b1b; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Facebook Connections</h1>
                    <div class="stats">
                        <strong>📊 Total Connections:</strong> {len(tokens)} | 
                        <strong>✅ Active:</strong> {active_count} | 
                        <strong>❌ Revoked:</strong> {len(tokens) - active_count}
                    </div>
                    
                    <div id="message"></div>
                    
                    {connections_html if connections_html else "<p style='color:#6b7280; padding:20px; text-align:center;'>No connections found</p>"}
                    
                    <div style="margin-top:30px; padding-top:20px; border-top:1px solid #e5e7eb;">
                        <a href="/" class="button">← Back to Home</a>
                        <a href="/logout" class="button button-danger">Logout All</a>
                    </div>
                </div>
                
                <script>
                    async function revokeConnection(fbUserId) {{
                        if (!confirm('Are you sure you want to revoke access for this connection?')) {{
                            return;
                        }}
                        
                        const messageEl = document.getElementById('message');
                        messageEl.style.display = 'block';
                        messageEl.className = '';
                        messageEl.textContent = 'Revoking access...';
                        
                        try {{
                            const response = await fetch('/admin/facebook/logout', {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type': 'application/json'
                                }},
                                body: JSON.stringify({{ fb_user_id: fbUserId }})
                            }});
                            
                            const data = await response.json();
                            
                            if (data.success) {{
                                messageEl.className = 'success';
                                messageEl.textContent = '✅ Access revoked successfully! Reloading...';
                                setTimeout(() => {{
                                    window.location.reload();
                                }}, 1500);
                            }} else {{
                                messageEl.className = 'error';
                                messageEl.textContent = '❌ Error: ' + (data.error || 'Failed to revoke access');
                            }}
                        }} catch (error) {{
                            messageEl.className = 'error';
                            messageEl.textContent = '❌ Error: ' + error.message;
                        }}
                    }}
                </script>
            </body>
            </html>
        """)
    except Exception as e:
        logger.error(f"Failed to list connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/admin/facebook/reconnect")
async def admin_reconnect(user_id: Optional[str] = Query(None), fb_user_id: Optional[str] = Query(None)):
    """
    Trigger re-authentication flow for a user.
    
    Query params:
        user_id: App user ID (preferred)
        fb_user_id: Facebook user ID (alternative)
    """
    if not settings.is_oauth_configured:
        raise HTTPException(status_code=503, detail="OAuth not configured")
    
    try:
        # Revoke existing token if found
        db = get_db_session()
        try:
            query = db.query(FacebookToken)
            if fb_user_id:
                query = query.filter(FacebookToken.fb_user_id == fb_user_id)
            elif user_id:
                query = query.filter(FacebookToken.user_id == user_id)
            
            existing = query.first()
            if existing:
                existing.revoked = True
                db.commit()
        finally:
            db.close()
        
        # Generate new state and redirect
        state = oauth_service.generate_state(user_id=user_id)
        auth_url = oauth_service.get_authorization_url(state)
        
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Failed to reconnect: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logout")
async def logout_page():
    """Display logout/revoke access page."""
    # Check if there are any active connections
    db = get_db_session()
    try:
        active_tokens = db.query(FacebookToken).filter(FacebookToken.revoked == False).all()
        has_connections = len(active_tokens) > 0
        
        if not has_connections:
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>No Active Connections</title>
                    <style>
                        * { margin: 0; padding: 0; box-sizing: border-box; }
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            min-height: 100vh;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            padding: 20px;
                        }
                        .container {
                            background: white;
                            border-radius: 20px;
                            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                            padding: 40px;
                            max-width: 500px;
                            width: 100%;
                            text-align: center;
                        }
                        h1 { color: #333; margin-bottom: 20px; }
                        p { color: #666; margin-bottom: 30px; }
                        .button {
                            display: inline-block;
                            padding: 12px 24px;
                            background: #667eea;
                            color: white;
                            text-decoration: none;
                            border-radius: 8px;
                            font-weight: 600;
                            transition: all 0.3s ease;
                        }
                        .button:hover { background: #5568d3; transform: translateY(-2px); }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>No Active Connections</h1>
                        <p>You don't have any active Facebook connections to revoke.</p>
                        <a href="/" class="button">Back to Home</a>
                    </div>
                </body>
                </html>
                """
            )
        
        # Show logout confirmation page
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Logout & Revoke Access</title>
                <style>
                    * { margin: 0; padding: 0; box-sizing: border-box; }
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        padding: 20px;
                    }
                    .container {
                        background: white;
                        border-radius: 20px;
                        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                        padding: 40px;
                        max-width: 500px;
                        width: 100%;
                        text-align: center;
                    }
                    .warning-icon {
                        width: 80px;
                        height: 80px;
                        background: #f59e0b;
                        border-radius: 50%;
                        margin: 0 auto 20px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 40px;
                        color: white;
                    }
                    h1 { color: #333; margin-bottom: 10px; }
                    .subtitle { color: #666; margin-bottom: 30px; }
                    .warning {
                        background: #fef3c7;
                        border-left: 4px solid #f59e0b;
                        padding: 15px;
                        margin: 20px 0;
                        text-align: left;
                        border-radius: 4px;
                    }
                    .warning h3 { color: #d97706; margin-bottom: 10px; font-size: 16px; }
                    .warning ul { margin-left: 20px; color: #92400e; }
                    .button {
                        display: inline-block;
                        padding: 12px 24px;
                        text-decoration: none;
                        border-radius: 8px;
                        margin: 10px;
                        font-weight: 600;
                        transition: all 0.3s ease;
                        border: none;
                        cursor: pointer;
                        font-size: 14px;
                    }
                    .button-danger {
                        background: #dc2626;
                        color: white;
                    }
                    .button-danger:hover { background: #b91c1c; transform: translateY(-2px); }
                    .button-secondary {
                        background: #6b7280;
                        color: white;
                    }
                    .button-secondary:hover { background: #4b5563; }
                    #message {
                        margin-top: 20px;
                        padding: 15px;
                        border-radius: 8px;
                        display: none;
                    }
                    .success { background: #d1fae5; color: #065f46; }
                    .error { background: #fee2e2; color: #991b1b; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="warning-icon">⚠️</div>
                    <h1>Logout & Revoke Access</h1>
                    <p class="subtitle">This will disconnect your Facebook account from Meta Ads MCP</p>
                    
                    <div class="warning">
                        <h3>⚠️ What will happen:</h3>
                        <ul>
                            <li>Your access token will be revoked</li>
                            <li>All stored authentication data will be removed</li>
                            <li>The MCP server will lose access to your ad accounts</li>
                            <li>You'll need to reconnect to use the service again</li>
                        </ul>
                    </div>
                    
                    <div id="message"></div>
                    
                    <div style="margin-top: 30px;">
                        <button onclick="confirmRevoke()" class="button button-danger">Yes, Revoke Access</button>
                        <a href="/" class="button button-secondary">Cancel</a>
                    </div>
                </div>
                
                <script>
                    async function confirmRevoke() {
                        const messageEl = document.getElementById('message');
                        messageEl.style.display = 'block';
                        messageEl.className = '';
                        messageEl.textContent = 'Revoking access...';
                        
                        try {
                            const response = await fetch('/api/logout', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                }
                            });
                            
                            const data = await response.json();
                            
                            if (data.success) {
                                messageEl.className = 'success';
                                messageEl.innerHTML = '✅ Access revoked successfully!<br>Redirecting to home...';
                                setTimeout(() => {
                                    window.location.href = '/';
                                }, 2000);
                            } else {
                                messageEl.className = 'error';
                                messageEl.textContent = '❌ Error: ' + (data.error || 'Failed to revoke access');
                            }
                        } catch (error) {
                            messageEl.className = 'error';
                            messageEl.textContent = '❌ Error: ' + error.message;
                        }
                    }
                </script>
            </body>
            </html>
            """
        )
    finally:
        db.close()


@app.post("/api/logout")
async def api_logout():
    """API endpoint to revoke all active tokens for the current user."""
    db = get_db_session()
    try:
        # Get all active tokens
        active_tokens = db.query(FacebookToken).filter(FacebookToken.revoked == False).all()
        
        if not active_tokens:
            return JSONResponse({
                "success": True,
                "message": "No active tokens to revoke",
                "revoked_count": 0
            })
        
        # Revoke all tokens
        revoked_count = 0
        for token in active_tokens:
            token.revoked = True
            token.updated_at = datetime.now(timezone.utc)
            revoked_count += 1
        
        db.commit()
        
        logger.info(f"Revoked {revoked_count} token(s) via logout")
        
        return JSONResponse({
            "success": True,
            "message": f"Successfully revoked {revoked_count} access token(s)",
            "revoked_count": revoked_count
        })
    except Exception as e:
        db.rollback()
        logger.error(f"Logout failed: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.web_server_host,
        port=settings.web_server_port,
        log_level=settings.log_level.lower()
    )

