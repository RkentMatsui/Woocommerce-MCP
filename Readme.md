# WooCommerce MCP Server

An MCP (Model Context Protocol) server for WooCommerce, providing tools for product management, order analysis, sales trends, and integration with the Nova B2B theme.

## Features

### Core WooCommerce Tools
- **Get Products**: Retrieve product lists with details (ID, name, SKU, price, stock).
- **Get Orders**: Fetch recent orders with status and totals.
- **Analyze Sales Trends**: Get revenue analysis and daily averages over a time period.
- **Low Stock Alerts**: Identify products that need reordering.
- **Order Management**: Update status, add notes, and create refunds.
- **Marketing**: Create and manage coupons.

### Support & CRM Integration
- **Zendesk Tickets**: Search for support tickets, get details, and retrieve comment history.
- **Support Responses**: Add public replies or internal notes directly to tickets.
- **Zendesk Sell (CRM)**: Search for leads, contacts, and deals. Retrieve specific custom fields like 'Industry', 'Sample Box', 'Product', and 'Service'.
- **User Management**: Search and identify customers within the Zendesk system.
- **Streak CRM**: Retrieve box details for deal tracking (Legacy support).

### Nova B2B Integration Tools
- **Live Order Feed**: Track physical material details and production queue.
- **Signage Calculator Pricing**: Retrieve pricing tables for letters, logos, and quantity discounts.
- **Production Timeline**: Detailed milestones and estimated lead times.
- **Design Approvals**: Access shared links to mockups and submit approval status.
- **Product Knowledge**: Access technical specs, installation guides, and FAQs.
- **Quotes & Estimating**: Retrieve and search signage quotes by user or business ID.
- **Customer Lookup**: Find business information by email or user ID.
- **OCR Integration**: Extract contact details from business card images.
- **Analytics**: Analyze refund patterns and identify inactive clients.

## Prerequisites

- Python 3.10 or higher
- WooCommerce store with REST API access
- Nova B2B Theme (optional, for custom tools)

## Setup Instructions

### 1. Create Virtual Environment

Start by creating and activating a Python virtual environment:

```powershell
# Create venv
python -m venv venv

# Activate venv (Windows)
.\venv\Scripts\activate
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory (or edit the existing one). The Nova tools require additional authentication for sensitive data.

```ini
# WooCommerce API (Standard)
WC_URL=https://your-store.com/
WC_CONSUMER_KEY=ck_your_consumer_key
WC_CONSUMER_SECRET=cs_your_consumer_secret

# Nova B2B Configuration (Custom Tools)
NOVA_API_KEY=your_custom_api_key
WP_USERNAME=admin_username
WP_APP_PASSWORD=xxxx_xxxx_xxxx_xxxx

# Zendesk Integration (Direct)
ZENDESK_EMAIL=your_email@example.com
ZENDESK_API_TOKEN=your_zendesk_api_token
ZENDESK_SELL_API_TOKEN=your_zendesk_sell_token
```

### 4. Test Connection

Verify your setup by running the connection test script:

```powershell
python test_connection.py
```

## Usage

### Running the Server

**Option 1: Stdio (Local Use with Claude Desktop)**

```powershell
python server.py
```

**Option 2: HTTP/SSE Server (Remote/Online Use)**

Run the FastAPI server which exposes the MCP server via SSE at `http://localhost:8000/sse`:

```powershell
python main.py
```

**Option 3: Docker (Production)**

Build and run the container:

```powershell
docker build -t nova-mcp-server .
docker run -p 8000:8000 --env-file .env nova-mcp-server
```

### Connecting to Claude Desktop (Stdio)

Add the following to your Claude Desktop configuration (usually `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "woocommerce": {
      "command": "python.exe",
      "args": [
        "f:\\Work\\Nova\\wc-mcp-server\\server.py"
      ],
      "env": {
        "WC_URL": "your_url",
        "WC_CONSUMER_KEY": "your_key",
        "WC_CONSUMER_SECRET": "your_secret",
        "NOVA_API_KEY": "your_api_key",
        "WP_USERNAME": "your_username",
        "WP_APP_PASSWORD": "your_app_password",
        "ZENDESK_EMAIL": "your_email",
        "ZENDESK_API_TOKEN": "your_token"
      }
    }
  }
}
```
*Note: Make sure to use the absolute path to your python executable if it's not in your PATH.*
