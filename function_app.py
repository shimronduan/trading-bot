import azure.functions as func
import logging
from decimal import Decimal
from binance.spot import Spot as Client
from binance.error import ClientError, ServerError
import logging
import json  # Add this import at the top of your file


# Optional: Configure logging to see more details from the binance-connector library
# logging.basicConfig(level=logging.DEBUG)

# --- Configuration ---
# IMPORTANT: Replace with your actual API Key and Secret Key
# Ensure your API key has "Enable Spot & Margin Trading" permissions.
# NEVER share your API keys publicly.
API_KEY = ""
API_SECRET = ""
SYMBOL = "BTCUSDT"



app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="trigger_bot")
def trigger_bot(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    spot_client = initialize_client(API_KEY, API_SECRET)
    balance = get_btc_balance(spot_client)
    if spot_client:
        # --- Choose an action ---
        # Example: Check BTC Balance
        # current_btc_balance = get_btc_balance(spot_client)
        # print(f"Your current free BTC balance is: {current_btc_balance}")

        # To sell all BTC (now with LOT_SIZE adjustment):
        # sell_all_btc(spot_client)

        # To buy BTC with a specific amount of USDT (e.g., 10 USDT):
        # Make sure you have sufficient USDT balance in your spot account.
        # And that the amount meets MIN_NOTIONAL (usually >= 5 or 10 USDT).
        # amount_usdt = 10.0
        # buy_btc_with_usdt(spot_client, amount_usdt)
        logging.info("\nScript finished.")
        logging.info("Always test with small amounts first and understand the risks involved in trading.")
        logging.info("Ensure your API Keys have the correct permissions and are kept secure.")
    return func.HttpResponse(
        json.dumps(spot_client.account(), indent=4),  # Convert the dictionary to a JSON string
        status_code=200,
        mimetype="application/json"  # Set the correct MIME type for JSON
    )


def initialize_client(api_key, api_secret):
    """Initializes and returns the Binance Spot client."""
    if api_key == "YOUR_API_KEY" or api_secret == "YOUR_API_SECRET":
        logging.info("IMPORTANT: Please replace 'YOUR_API_KEY' and 'YOUR_API_SECRET' with your actual Binance API keys.")
        return None
    return Client(api_key, api_secret)


def get_btc_balance(client: Client):
    """
    Fetches the free (available for trading) BTC balance.
    Returns the free BTC balance as a float, or 0.0 if not found or an error occurs.
    """
    if not client:
        return 0.0
    try:
        account_info = client.account()
        balances = account_info.get('balances', [])
        for asset_balance in balances:
            if asset_balance['asset'] == 'BTC':
                return float(asset_balance['free'])
        logging.info("BTC balance not found in your account.")
        return 0.0
    except (ClientError, ServerError) as e:
        logging.info(f"Error fetching BTC balance: {e}")
        return 0.0
    except Exception as e:
        logging.info(f"An unexpected error occurred while fetching BTC balance: {e}")
        return 0.0


def get_symbol_lot_size_filter(client: Client, symbol: str):
    """
    Fetches the LOT_SIZE filter details for a given symbol.

    Args:
        client: The Binance Spot client instance.
        symbol: The trading symbol (e.g., "BTCUSDT").

    Returns:
        A dictionary with 'minQty', 'maxQty', 'stepSize' as Decimals, or None if error.
    """
    if not client:
        return None
    try:
        exchange_info = client.exchange_info(symbol=symbol)
        for s_filter in exchange_info['symbols'][0]['filters']:
            if s_filter['filterType'] == 'LOT_SIZE':
                return {
                    'minQty': Decimal(s_filter['minQty']),
                    'maxQty': Decimal(s_filter['maxQty']),
                    'stepSize': Decimal(s_filter['stepSize'])
                }
        logging.info(f"LOT_SIZE filter not found for symbol {symbol}.")
        return None
    except (ClientError, ServerError) as e:
        logging.info(f"Error fetching exchange info for {symbol}: {e}")
        return None
    except Exception as e:
        logging.info(f"An unexpected error occurred while fetching exchange info: {e}")
        return None


def adjust_quantity_to_lot_size(quantity: Decimal, lot_size_filter: dict) -> Decimal:
    """
    Adjusts the quantity to conform to the LOT_SIZE filter's stepSize.

    Args:
        quantity: The desired quantity as a Decimal.
        lot_size_filter: The lot size filter details from get_symbol_lot_size_filter.

    Returns:
        The adjusted quantity as a Decimal.
    """
    min_qty = lot_size_filter['minQty']
    step_size = lot_size_filter['stepSize']

    if quantity < min_qty:
        return Decimal('0')  # Cannot meet minQty

    # Adjust for stepSize: floor(quantity / stepSize) * stepSize
    # Or more precisely for Decimals: (quantity // step_size) * step_size if step_size is a power of 10
    # A more general way is to quantize
    # number_of_steps = (quantity - min_qty) // step_size
    # adjusted_quantity = min_qty + number_of_steps * step_size
    # Simpler approach for flooring to step_size:
    adjusted_quantity = (quantity // step_size) * step_size

    return adjusted_quantity


def sell_all_btc(client: Client):
    """
    Sells all available BTC at the current market price,
    adjusting for LOT_SIZE filter.
    """
    if not client:
        logging.info("Client not initialized. Cannot sell BTC.")
        return

    btc_balance_float = get_btc_balance(client)
    if btc_balance_float <= 0:
        logging.info("No BTC balance to sell or error fetching balance.")
        return

    btc_balance_decimal = Decimal(str(btc_balance_float))  # Use string conversion for Decimal accuracy
    logging.info(f"Original BTC balance: {btc_balance_decimal}")

    lot_size_filter = get_symbol_lot_size_filter(client, SYMBOL)
    if not lot_size_filter:
        logging.info("Could not retrieve LOT_SIZE filter. Aborting sell.")
        return

    min_qty = lot_size_filter['minQty']
    step_size = lot_size_filter['stepSize']
    logging.info(f"LOT_SIZE for {SYMBOL}: minQty={min_qty}, stepSize={step_size}")

    if btc_balance_decimal < min_qty:
        logging.info(f"BTC balance {btc_balance_decimal} is less than minQty {min_qty}. Cannot sell.")
        return

    # Adjust quantity
    # The quantity to be ordered must be greater than minQty.
    # The quantity must be an increment of stepSize.
    # (quantity-minQty) % stepSize == 0
    # A common way to adjust is to floor the quantity to the nearest stepSize.
    # quantity_to_sell = floor(balance / stepSize) * stepSize

    # For Decimal, quantize can be used if step_size is like '0.00001'
    # Or use the formula: (value // step) * step
    quantity_to_sell = (btc_balance_decimal // step_size) * step_size

    # Ensure the final quantity is not less than min_qty after adjustment
    if quantity_to_sell < min_qty:
        logging.info(f"Adjusted BTC quantity {quantity_to_sell} is less than minQty {min_qty}. Cannot sell.")
        return

    # Also, the quantity to sell must be > 0
    if quantity_to_sell <= Decimal('0'):
        logging.info(f"Adjusted BTC quantity {quantity_to_sell} is zero or less. Nothing to sell.")
        return

    logging.info(f"Attempting to sell adjusted quantity: {quantity_to_sell} BTC...")
    try:
        params = {
            'symbol': SYMBOL,
            'side': 'SELL',
            'type': 'MARKET',
            'quantity': str(quantity_to_sell),  # Send as string
        }
        response = client.new_order(**params)
        logging.info("Successfully placed sell order:")
        logging.info(response)
    except (ClientError, ServerError) as e:
        logging.info(f"Error placing sell order: {e}")
    except Exception as e:
        logging.info(f"An unexpected error occurred during sell order: {e}")


def buy_btc_with_usdt(client: Client, usdt_amount_to_spend: float):
    """
    Buys BTC with a specified amount of USDT at the current market price.
    """
    if not client:
        logging.info("Client not initialized. Cannot buy BTC.")
        return

    # The MIN_NOTIONAL filter applies to quoteOrderQty for market orders.
    # We should also check this, but for now, let's assume usdt_amount_to_spend is sufficient (e.g. > 10 USDT).
    # A common MIN_NOTIONAL value is 5 or 10 USDT.
    min_notional_value = Decimal('5.0')  # Example, you might want to fetch this too.
    if Decimal(str(usdt_amount_to_spend)) < min_notional_value:
        logging.info(
            f"USDT amount {usdt_amount_to_spend} may be below MIN_NOTIONAL filter (typically around {min_notional_value} USDT).")
        # Consider not stopping here, but warning, as Binance might still accept slightly lower depending on exact rules.
        # However, it's good practice:
        # return

    if usdt_amount_to_spend <= 0:
        logging.info("USDT amount to spend must be positive.")
        return

    logging.info(f"Attempting to buy BTC with {usdt_amount_to_spend} USDT...")
    try:
        params = {
            'symbol': SYMBOL,
            'side': 'BUY',
            'type': 'MARKET',
            'quoteOrderQty': usdt_amount_to_spend,  # This is a float or string
        }
        response = client.new_order(**params)
        logging.info("Successfully placed buy order:")
        logging.info(response)
    except (ClientError, ServerError) as e:
        logging.info(f"Error placing buy order: {e} (usdt_amount_to_spend: {usdt_amount_to_spend})")
        # If error is MIN_NOTIONAL: e.g., (400, -1013, 'Filter failure: MIN_NOTIONAL', ...)
        # If the user tries to spend too little USDT (e.g., 1 USDT), this will fail.
    except Exception as e:
        logging.info(f"An unexpected error occurred during buy order: {e}")
