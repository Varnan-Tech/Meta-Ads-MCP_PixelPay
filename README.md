# Meta Ads MCP Server

An MCP (Model Context Protocol) server that enables AI assistants like Claude to interact with Meta Ads (Facebook/Instagram) programmatically. Manage your ad campaigns through natural language conversations.

## Features

### Core Features (MVP)
- 🔐 **Authentication & Token Management** - Secure storage and validation of Meta API tokens
- 📊 **Account Management** - List and view ad accounts with details
- 🎯 **Campaign Operations** - Create, read, update campaigns with full CRUD support
- 📈 **Performance Analytics** - Get insights, metrics, and ROAS calculations
- 🎯 **Targeting Discovery** - Search interests, demographics, and locations
- 🤖 **AI-Powered Analysis** - Automated campaign analysis with recommendations

### Supported Operations

#### Account Management
- `get_ad_accounts` - List all accessible Meta ad accounts
- `get_account_info` - Get detailed account information

#### Campaign Management
- `get_campaigns` - List campaigns with filtering options
- `get_campaign_details` - Get detailed campaign information
- `create_campaign` - Create new campaigns with objectives and budgets
- `update_campaign` - Update campaign status, budget, or settings

#### Analytics & Insights
- `get_insights` - Get performance metrics for campaigns, ad sets, or ads
- `analyze_campaigns` - AI-powered campaign analysis with recommendations

#### Targeting
- `search_interests` - Search for interest-based targeting options
- `search_demographics` - Search demographic targeting options
- `search_locations` - Search geographic targeting locations

## Installation

### Prerequisites
- Python 3.10 or higher
- Meta Ads API access token (get from [Facebook Developers](https://developers.facebook.com))

### Quick Setup

1. **Clone and install:**
```bash
git clone <repository-url>
cd meta-ads-mcp
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp env.example .env
# Edit .env and add your Meta access token:
# META_ACCESS_TOKEN=your_access_token_here
```

3. **Install the package:**
```bash
pip install -e .
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Meta API Configuration (Required)
META_ACCESS_TOKEN=your_access_token_here
META_APP_ID=your_app_id
META_APP_SECRET=your_app_secret

# Default Ad Account (Optional)
DEFAULT_AD_ACCOUNT=act_123456789

# Environment Settings
ENVIRONMENT=development
LOG_LEVEL=INFO

# Rate Limiting (Optional)
MAX_REQUESTS_PER_HOUR=200

# Cache Settings (Optional)
CACHE_TTL=300
ENABLE_CACHE=true
```

### Meta API Permissions

Your access token needs specific permissions based on the operations you want to perform. Here's a comprehensive breakdown:

#### Required Permissions by Operation

**Basic Account Access:**
- `ads_read` - Required for all ad account operations
- `ads_management` - Required for creating/modifying campaigns

**Analytics & Insights:**
- `ads_read` - Read campaign performance data
- `read_insights` - Access detailed performance metrics

**Campaign Management:**
- `ads_management` - Create, update, and manage campaigns
- `ads_read` - Read campaign information

**Targeting Operations:**
- `ads_management` - Access targeting search and audience estimation
- `ads_read` - Read targeting options

#### Complete Permission List

For full functionality, your token should have these permissions:
```
ads_management    - Full campaign CRUD operations
ads_read          - Read campaigns, ads, and account data
read_insights     - Access performance analytics
```

#### Permission Error Messages

If you see these errors, check your token permissions:

- **"Access denied... ads_management or ads_read permission"** → Add `ads_management` or `ads_read`
- **"Application request limit reached"** → You've hit Meta's API rate limits (200 req/hour)
- **"Invalid access token"** → Token expired or malformed

### Getting Your Meta Access Token

1. Go to [Facebook Developers](https://developers.facebook.com)
2. Create an app or use an existing one
3. Add the **Marketing API** product
4. Generate an access token with the permissions listed above

## Usage with Claude

### Claude Desktop Configuration

Add to your Claude Desktop configuration (`~/.config/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "meta-ads": {
      "command": "python",
      "args": ["/path/to/meta-ads-mcp/src/server.py"]
    }
  }
}
```

### Cursor Configuration

Add to your Cursor MCP configuration:

```json
{
  "mcpServers": {
    "meta-ads": {
      "command": "python",
      "args": ["/path/to/meta-ads-mcp/src/server.py"]
    }
  }
}
```

### Example Conversations

Once configured, you can interact with Meta Ads naturally:

**List your ad accounts:**
```
Claude: "Show me my ad accounts"
```

**View campaign performance:**
```
Claude: "How are my campaigns performing this month?"
```

**Create a new campaign:**
```
Claude: "Create a new campaign for summer shoes with a $50 daily budget"
```

**Get AI analysis:**
```
Claude: "Analyze my campaigns and tell me which ones to pause"
```

## Development

### Project Structure

```
meta-ads-mcp/
├── src/
│   ├── server.py              # Main MCP server
│   ├── auth/
│   │   └── token_manager.py   # Token storage & validation
│   ├── tools/
│   │   ├── accounts.py        # Account management tools
│   │   ├── campaigns.py       # Campaign CRUD tools
│   │   ├── insights.py        # Analytics tools
│   │   └── targeting.py       # Targeting search tools
│   ├── core/
│   │   ├── analyzer.py        # AI analysis engine
│   │   ├── validators.py      # Input validation
│   │   └── formatters.py      # Response formatting
│   ├── api/
│   │   └── client.py          # Meta API wrapper
│   ├── config/
│   │   ├── settings.py        # App configuration
│   │   └── constants.py       # API constants
│   └── utils/
│       └── logger.py          # Logging utilities
├── tests/                     # Test suite
├── docs/                      # Documentation
├── examples/                  # Usage examples
├── requirements.txt           # Dependencies
└── README.md                 # This file
```

### Running Tests

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

### Code Quality

```bash
# Format code
black src/

# Lint code
ruff src/

# Type checking
mypy src/
```

## API Reference

### Tool Specifications

#### get_ad_accounts
List all accessible Meta ad accounts.

**Parameters:** None

**Returns:**
```json
{
  "success": true,
  "accounts": [
    {
      "id": "act_123456789",
      "name": "My Business Ads",
      "account_id": "123456789",
      "currency": "USD",
      "status": "ACTIVE",
      "balance": "$0.00"
    }
  ],
  "count": 1
}
```

#### create_campaign
Create a new ad campaign.

**Parameters:**
- `account_id` (string, required): Meta ad account ID
- `name` (string, required): Campaign name
- `objective` (string, required): Campaign objective (OUTCOME_AWARENESS, OUTCOME_TRAFFIC, etc.)
- `daily_budget` (integer, optional): Daily budget in cents
- `lifetime_budget` (integer, optional): Lifetime budget in cents
- `status` (string, optional): Campaign status (ACTIVE or PAUSED)

**Returns:**
```json
{
  "success": true,
  "campaign": {
    "id": "120202345678901234",
    "name": "Summer Sale 2025",
    "status": "PAUSED",
    "objective": "OUTCOME_SALES",
    "daily_budget": "$100.00",
    "created_time": "Oct 21, 2025"
  },
  "message": "Campaign created successfully. Status is PAUSED - activate when ready."
}
```

#### get_insights
Get performance metrics for campaigns, ad sets, or ads.

**Parameters:**
- `object_id` (string, required): ID of campaign, ad set, ad, or account
- `time_range` (string, optional): Time range preset (today, yesterday, last_7d, etc.)
- `breakdown` (string, optional): Optional breakdown dimension (see breakdown options below)

**Breakdown Options:**
The `breakdown` parameter allows you to segment your insights data. Common options include:
- `age` - Break down by age groups
- `gender` - Break down by gender
- `country` - Break down by country
- `region` - Break down by geographic region
- `placement` - Break down by ad placement (feed, stories, etc.)
- `publisher_platform` - Break down by platform (facebook, instagram, etc.)
- `device_platform` - Break down by device type (mobile, desktop)
- `platform_position` - Break down by specific platform positions

**Note:** Meta API automatically breaks down data by date when requesting insights over a time range. You don't need a 'day' or 'date' breakdown option.

**Returns:**
```json
{
  "success": true,
  "insights": [
    {
      "date_start": "2025-01-01",
      "date_stop": "2025-01-01",
      "spend": "150.00",
      "impressions": "5000",
      "clicks": "150",
      "ctr": "3.00%",
      "cpc": "1.00",
      "cpm": "30.00",
      "conversions": "15",
      "conversion_value": "750.00",
      "roas": "5.00x"
    }
  ]
}
```

#### analyze_campaigns
Get AI-powered campaign analysis.

**Parameters:**
- `account_id` (string, required): Meta ad account ID
- `time_range` (string, optional): Time range (last_7d, last_30d, etc.)
- `focus` (string, optional): Analysis focus (performance, budget, creative, targeting)

**Returns:**
```json
{
  "success": true,
  "analysis": {
    "summary": {
      "total_spend": "$1,250.50",
      "total_conversions": 87,
      "average_roas": "4.23x",
      "account_health": "Good"
    },
    "top_performers": [...],
    "underperformers": [...],
    "recommendations": [...],
    "action_items": [...]
  }
}
```

## Troubleshooting

### Common Issues

**"No access token available"**
- Ensure `META_ACCESS_TOKEN` is set in your `.env` file
- Check that your token has the required permissions

**"Invalid account ID format"**
- Account IDs must start with `act_` (e.g., `act_123456789`)

**"Token validation failed"**
- Check that your token is not expired
- Verify your app has the required permissions
- Try regenerating the token in Facebook Developers

**"API rate limit exceeded"**
- The server respects Meta's rate limits (200 requests/hour by default)
- Wait a few minutes before retrying

### Debug Mode

Enable debug logging by setting:
```bash
LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue in the GitHub repository
- Check the troubleshooting section above
- Review the Meta Marketing API documentation

## Changelog

### Version 1.0.0 (MVP)
- Initial release with 8 core features
- Token management and secure storage
- Full campaign CRUD operations
- Performance analytics and insights
- Targeting search capabilities
- AI-powered campaign analysis
- Comprehensive error handling

---

**Ready to manage your Meta ads with AI?** 🚀

Configure your access token and start asking Claude about your campaigns!
