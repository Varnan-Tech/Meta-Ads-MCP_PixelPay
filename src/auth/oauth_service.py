"""
Facebook OAuth service for handling authentication flows.
"""
import secrets
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

try:
    from ..config.settings import settings
    from ..utils.logger import logger
    from .database import get_db_session, OAuthState, FacebookToken
    from .encryption import get_encryption
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from config.settings import settings
    from utils.logger import logger
    from auth.database import get_db_session, OAuthState, FacebookToken
    from auth.encryption import get_encryption


class FacebookOAuthService:
    """Service for handling Facebook OAuth flows."""
    
    def __init__(self):
        self.encryption = get_encryption()
        self.base_url = f"https://graph.facebook.com/{settings.fb_api_version}"
    
    def generate_state(self, user_id: Optional[str] = None) -> str:
        """
        Generate a secure state token for OAuth CSRF protection.
        
        Args:
            user_id: Optional app user ID
            
        Returns:
            State token string
        """
        state = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.oauth_state_ttl_minutes)
        
        db = get_db_session()
        try:
            oauth_state = OAuthState(
                state=state,
                user_id=user_id,
                expires_at=expires_at
            )
            db.add(oauth_state)
            db.commit()
            logger.info(f"Generated OAuth state for user: {user_id}")
            return state
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to generate state: {e}")
            raise
        finally:
            db.close()
    
    def validate_state(self, state: str) -> Optional[str]:
        """
        Validate and consume an OAuth state token.
        
        Args:
            state: State token to validate
            
        Returns:
            User ID if valid, None otherwise
        """
        db = get_db_session()
        try:
            oauth_state = db.query(OAuthState).filter(OAuthState.state == state).first()
            
            if not oauth_state:
                logger.warning(f"Invalid state token: {state}")
                return None
            
            # Handle naive datetimes in DB by assuming UTC
            expires_at = oauth_state.expires_at
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at and expires_at < datetime.now(timezone.utc):
                logger.warning(f"Expired state token: {state}")
                db.delete(oauth_state)
                db.commit()
                return None
            
            user_id = oauth_state.user_id
            db.delete(oauth_state)
            db.commit()
            logger.info(f"Validated and consumed state token for user: {user_id}")
            return user_id
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to validate state: {e}")
            return None
        finally:
            db.close()
    
    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate Facebook OAuth authorization URL.
        
        Uses implicit OAuth flow (response_type=token) like Pipeboard's implementation.
        This works better for local/desktop apps and avoids scope validation issues.
        
        Args:
            state: Optional CSRF state token (not always needed for implicit flow)
            
        Returns:
            Authorization URL
        """
        # Use scopes as configured, or default to required scopes for ad account access
        scopes = settings.fb_oauth_scopes
        if not scopes or scopes == "public_profile":
            # Fallback to complete scopes for full ad account access
            # ads_management: Required to access and manage ad accounts
            # business_management: Access business-owned ad accounts
            # pages_show_list: Access Facebook Pages
            # read_insights: Read ad performance metrics
            # public_profile: Basic user info
            scopes = "ads_management,business_management,pages_show_list,read_insights,public_profile"
        
        params = {
            "client_id": settings.fb_app_id,
            "redirect_uri": settings.fb_redirect_uri,
            "scope": scopes,
            "response_type": "token"  # Implicit flow - token in URL fragment
        }
        
        # Add state if provided (optional for implicit flow)
        if state:
            params["state"] = state
        
        url = f"https://www.facebook.com/{settings.fb_api_version}/dialog/oauth"
        return f"{url}?{urlencode(params)}"
    
    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for short-lived access token.
        
        Args:
            code: Authorization code from callback
            
        Returns:
            Token response with access_token and expires_in
        """
        url = f"{self.base_url}/oauth/access_token"
        params = {
            "client_id": settings.fb_app_id,
            "client_secret": settings.fb_app_secret,
            "redirect_uri": settings.fb_redirect_uri,
            "code": code
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                logger.error(f"Token exchange error: {data['error']}")
                raise Exception(f"Facebook API error: {data['error'].get('message', 'Unknown error')}")
            
            return data
        except requests.RequestException as e:
            logger.error(f"Failed to exchange code for token: {e}")
            raise
    
    def exchange_short_token_for_long(self, short_token: str) -> Dict[str, Any]:
        """
        Exchange short-lived token for long-lived token.
        
        Args:
            short_token: Short-lived access token
            
        Returns:
            Token response with access_token and expires_in
        """
        url = f"{self.base_url}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": settings.fb_app_id,
            "client_secret": settings.fb_app_secret,
            "fb_exchange_token": short_token
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                logger.error(f"Long token exchange error: {data['error']}")
                raise Exception(f"Facebook API error: {data['error'].get('message', 'Unknown error')}")
            
            return data
        except requests.RequestException as e:
            logger.error(f"Failed to exchange for long token: {e}")
            raise
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get Facebook user information.
        
        Args:
            access_token: Access token
            
        Returns:
            User info dict with id and name
        """
        url = f"{self.base_url}/me"
        params = {
            "access_token": access_token,
            "fields": "id,name"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get user info: {e}")
            raise
    
    def _fetch_paginated_data(self, url: str, params: Dict[str, Any], max_pages: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch all pages of data from a paginated Meta API endpoint.

        Args:
            url: Initial URL to fetch
            params: Query parameters
            max_pages: Maximum number of pages to fetch (safety limit)

        Returns:
            List of all items from all pages
        """
        all_data = []
        current_url = url
        current_params = params.copy()
        page_count = 0

        while current_url and page_count < max_pages:
            try:
                response = requests.get(current_url, params=current_params if page_count == 0 else None, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Add items from this page
                items = data.get("data", [])
                all_data.extend(items)
                page_count += 1

                logger.debug(f"Fetched page {page_count} with {len(items)} items (total: {len(all_data)})")

                # Check for next page
                paging = data.get("paging", {})
                current_url = paging.get("next")
                current_params = None  # Next URL already has params

                if not current_url:
                    break

            except Exception as e:
                logger.warning(f"Error fetching page {page_count + 1}: {e}")
                break

        logger.info(f"Fetched {len(all_data)} total items across {page_count} pages")
        return all_data

    def get_ad_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Get user's ad accounts with pagination support.

        Uses business_management permission to access ad accounts through businesses.
        Falls back to direct /me/adaccounts if business_management not available.

        Args:
            access_token: Access token

        Returns:
            List of ad account dicts
        """
        formatted_accounts = []

        # Method 1: Try getting through businesses (with business_management permission)
        try:
            # Get user's businesses (with pagination)
            businesses_url = f"{self.base_url}/me/businesses"
            businesses_params = {
                "access_token": access_token,
                "fields": "id,name",
                "limit": 100  # Request more per page
            }

            logger.info("Fetching businesses for ad account access")
            businesses = self._fetch_paginated_data(businesses_url, businesses_params)
            logger.info(f"Found {len(businesses)} businesses")

            # For each business, get BOTH owned AND client ad accounts (with pagination)
            for business in businesses:
                business_id = business.get("id")
                business_name = business.get("name", "Unknown")

                all_business_accounts = []
                owned_count = 0
                client_count = 0

                # 1. Fetch OWNED ad accounts
                owned_accounts_url = f"{self.base_url}/{business_id}/owned_ad_accounts"
                owned_params = {
                    "access_token": access_token,
                    "fields": "id,name,account_id,currency,account_status",
                    "limit": 100  # Request more per page
                }

                try:
                    logger.debug(f"Fetching owned ad accounts for business: {business_name} ({business_id})")
                    owned_accounts = self._fetch_paginated_data(owned_accounts_url, owned_params)
                    all_business_accounts.extend(owned_accounts)
                    owned_count = len(owned_accounts)
                    logger.info(f"Found {owned_count} owned accounts for business {business_name}")
                except Exception as e:
                    logger.warning(f"Failed to get owned accounts for business {business_id}: {e}")

                # 2. Fetch CLIENT ad accounts (agencies/partners managing client accounts)
                # Note: This doubles API calls per business but is necessary for full account access
                # Rate limit consideration: With business_management permission, typical limit is 200 calls/hour
                # For 50 businesses: 50 owned + 50 client = 100 calls (within limit)
                client_accounts_url = f"{self.base_url}/{business_id}/client_ad_accounts"
                client_params = {
                    "access_token": access_token,
                    # Using minimal fields for client accounts as some fields may have restricted permissions
                    "fields": "id,name,account_id,currency,account_status",
                    "limit": 100  # Request more per page
                }

                try:
                    logger.debug(f"Fetching client ad accounts for business: {business_name} ({business_id})")
                    client_accounts = self._fetch_paginated_data(client_accounts_url, client_params)
                    all_business_accounts.extend(client_accounts)
                    client_count = len(client_accounts)
                    logger.info(f"Found {client_count} client accounts for business {business_name}")
                except Exception as e:
                    # Client accounts may fail if business has no client relationships or restricted permissions
                    logger.debug(f"No client accounts or restricted access for business {business_id}: {e}")

                # 3. Format and add ALL accounts (owned + client) with error handling for field access
                for account in all_business_accounts:
                    try:
                        formatted_accounts.append({
                            "id": account.get("id"),
                            "name": account.get("name"),
                            "account_id": account.get("account_id"),
                            "currency": account.get("currency"),
                            # account_status may be restricted on some client accounts
                            "status": account.get("account_status"),
                            "business_id": business_id
                        })
                    except Exception as e:
                        logger.warning(f"Failed to format account {account.get('id', 'unknown')}: {e}")
                        continue

                logger.info(f"Total for business {business_name}: {owned_count} owned + {client_count} client = {len(all_business_accounts)} accounts")

        except Exception as e:
            logger.debug(f"Could not get ad accounts through businesses: {e}")

        # Method 2: Fallback to direct /me/adaccounts (if ads_management permission available)
        if not formatted_accounts:
            try:
                logger.info("Fetching ad accounts via direct /me/adaccounts endpoint")
                url = f"{self.base_url}/me/adaccounts"
                params = {
                    "access_token": access_token,
                    "fields": "id,name,account_id,currency,account_status",
                    "limit": 100  # Request more per page
                }

                accounts = self._fetch_paginated_data(url, params)

                formatted_accounts = [
                    {
                        "id": account.get("id"),
                        "name": account.get("name"),
                        "account_id": account.get("account_id"),
                        "currency": account.get("currency"),
                        "status": account.get("account_status")
                    }
                    for account in accounts
                ]
            except requests.RequestException as e:
                logger.warning(f"Failed to get ad accounts via direct method: {e}")

        return formatted_accounts
    
    def save_token(
        self,
        user_id: Optional[str],
        fb_user_id: str,
        access_token: str,
        expires_in: int,
        permissions: Optional[List[str]] = None,
        accounts: Optional[List[Dict[str, Any]]] = None
    ) -> FacebookToken:
        """
        Save encrypted token to database.
        
        Args:
            user_id: App user ID
            fb_user_id: Facebook user ID
            access_token: Plaintext access token
            expires_in: Token expiration in seconds
            permissions: List of granted permissions
            accounts: List of ad accounts
            
        Returns:
            Created FacebookToken record
        """
        # Encrypt token
        encrypted_token = self.encryption.encrypt(access_token)
        
        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        db = get_db_session()
        try:
            # Check if token already exists for this user
            existing = db.query(FacebookToken).filter(
                FacebookToken.fb_user_id == fb_user_id
            ).first()
            
            if existing:
                # Update existing token
                existing.encrypted_access_token = encrypted_token
                existing.expires_at = expires_at
                existing.permissions = permissions
                existing.accounts = accounts
                existing.revoked = False
                existing.updated_at = datetime.now(timezone.utc)
                db.commit()
                # Make attributes accessible before closing session
                result_id = existing.id
                result_fb_user_id = existing.fb_user_id
                logger.info(f"Updated token for FB user: {fb_user_id}")
                db.close()
                return existing
            else:
                # Create new token
                token_record = FacebookToken(
                    user_id=user_id,
                    fb_user_id=fb_user_id,
                    encrypted_access_token=encrypted_token,
                    expires_at=expires_at,
                    permissions=permissions,
                    accounts=accounts
                )
                db.add(token_record)
                db.commit()
                db.refresh(token_record)
                # Make attributes accessible before closing session
                result_id = token_record.id
                result_fb_user_id = token_record.fb_user_id
                logger.info(f"Saved new token for FB user: {fb_user_id}")
                db.close()
                return token_record
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save token: {e}")
            db.close()
            raise
    
    def get_token(self, user_id: Optional[str] = None, fb_user_id: Optional[str] = None) -> Optional[str]:
        """
        Get decrypted access token for user.
        
        When called without parameters, returns the most recent active token.
        
        Args:
            user_id: App user ID
            fb_user_id: Facebook user ID
            
        Returns:
            Decrypted access token or None
        """
        db = get_db_session()
        try:
            query = db.query(FacebookToken).filter(FacebookToken.revoked == False)
            
            if fb_user_id:
                query = query.filter(FacebookToken.fb_user_id == fb_user_id)
            elif user_id:
                query = query.filter(FacebookToken.user_id == user_id)
            else:
                # No parameters: get the most recent active token
                query = query.order_by(FacebookToken.created_at.desc())
            
            token_record = query.first()
            
            if not token_record:
                logger.debug("No active token found in database")
                return None
            
            # Check if expired (handle naive vs aware datetimes)
            expires_at = token_record.expires_at
            if expires_at:
                # If stored datetime is naive, assume UTC
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                if expires_at < datetime.now(timezone.utc):
                    logger.warning(f"Token expired for FB user: {token_record.fb_user_id}")
                    return None
            
            # Decrypt and return
            decrypted_token = self.encryption.decrypt(token_record.encrypted_access_token)
            logger.debug(f"Retrieved token for FB user: {token_record.fb_user_id}")
            return decrypted_token
        except Exception as e:
            logger.error(f"Failed to get token: {e}")
            return None
        finally:
            db.close()
    
    def refresh_token(self, token_record: FacebookToken) -> bool:
        """
        Refresh a long-lived token by re-exchanging it.
        
        Args:
            token_record: FacebookToken record to refresh
            
        Returns:
            True if refresh successful
        """
        try:
            # Decrypt current token
            current_token = self.encryption.decrypt(token_record.encrypted_access_token)
            
            # Exchange for new long token
            response = self.exchange_short_token_for_long(current_token)
            
            new_token = response.get("access_token")
            expires_in = response.get("expires_in", 5184000)  # Default 60 days
            
            # Update token record
            encrypted_token = self.encryption.encrypt(new_token)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            db = get_db_session()
            try:
                token_record.encrypted_access_token = encrypted_token
                token_record.expires_at = expires_at
                token_record.last_refreshed = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"Refreshed token for FB user: {token_record.fb_user_id}")
                return True
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to update refreshed token: {e}")
                return False
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            return False
    
    def revoke_token(self, fb_user_id: str) -> bool:
        """
        Mark token as revoked (e.g., on deauth).
        
        Args:
            fb_user_id: Facebook user ID
            
        Returns:
            True if revoked
        """
        db = get_db_session()
        try:
            token_record = db.query(FacebookToken).filter(
                FacebookToken.fb_user_id == fb_user_id
            ).first()
            
            if token_record:
                token_record.revoked = True
                token_record.updated_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"Revoked token for FB user: {fb_user_id}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to revoke token: {e}")
            return False
        finally:
            db.close()


# Global service instance
oauth_service = FacebookOAuthService()

