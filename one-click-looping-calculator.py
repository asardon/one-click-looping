import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
from scipy.optimize import fsolve, minimize

def find_flashloan_amount(flashloan_amount, user_init_coll_amount, cross_price, ltv, dex_slippage, dex_swap_fee, upfront_fee):
    sold_on_dex = flashloan_amount
    received_from_dex = sold_on_dex / cross_price * (1 - dex_slippage - dex_swap_fee)

    combined_pledge = user_init_coll_amount + received_from_dex

    upfront_fee_abs = combined_pledge * upfront_fee

    flashloan_amount_act = (combined_pledge - upfront_fee_abs) * cross_price * ltv

    return (flashloan_amount - flashloan_amount_act)**2

def calculate_open_position(current_price_coll_token, current_price_loan_token, user_init_coll_amount, ltv, apr, upfront_fee, tenor, myso_fee, dex_slippage, dex_swap_fee):
    cross_price = current_price_coll_token / current_price_loan_token
    
    # Calculate flashloan amount
    flashloan_amount_guess = user_init_coll_amount * cross_price / (1 - ltv)
    res = minimize(
            find_flashloan_amount,
            args=(user_init_coll_amount, cross_price, ltv, dex_slippage, dex_swap_fee, upfront_fee),
            x0=[flashloan_amount_guess])
    flashloan_amount_act = res["x"][0]

    # Calculate owed repayment amount
    owed_repayment = flashloan_amount_act * (1 + apr * tenor/365)

    # Amount that's sold on the DEX 
    sold_on_dex = flashloan_amount_act

    # Amount received from the DEX (after considering slippage and swap fee)
    received_from_dex = sold_on_dex / cross_price * (1 - dex_slippage - dex_swap_fee)

    combined_pledge = user_init_coll_amount + received_from_dex

    # Upfront fee
    upfront_fee_abs = combined_pledge * upfront_fee

    # Myso protocol fee
    myso_fee_abs = combined_pledge * myso_fee

    # total pledge and reclaimable
    final_pledge_and_reclaimable = combined_pledge - upfront_fee_abs - myso_fee_abs

    # Return results
    return flashloan_amount_act, owed_repayment, sold_on_dex, received_from_dex, combined_pledge, upfront_fee_abs, myso_fee_abs, final_pledge_and_reclaimable

def calculate_close_position(final_pledge_and_reclaimable, owed_repayment, final_price_coll_token, final_price_loan_token, dex_slippage, dex_swap_fee, gas_usd_cost):
    cross_price = final_price_coll_token / final_price_loan_token
    
    # Amount flashborrowed
    flashloan_amount = final_pledge_and_reclaimable

    # Amount that's sold on the DEX 
    sold_on_dex = flashloan_amount

    # Amount received from the DEX (after considering slippage and swap fee)
    received_from_dex = sold_on_dex * cross_price * (1 - dex_slippage - dex_swap_fee)

    # Amount left over after repay
    final_amount_after_close = received_from_dex - owed_repayment
    final_amount_after_close_net_of_gas_fees = final_amount_after_close - gas_usd_cost

    # Myso protocol fee
    rational_to_repay = final_amount_after_close > 0

    if not rational_to_repay:
        flashloan_amount = 0 
        sold_on_dex = 0
        received_from_dex = 0
        final_amount_after_close = 0
    
    # Return results
    return flashloan_amount, sold_on_dex, received_from_dex, final_amount_after_close, rational_to_repay, final_amount_after_close_net_of_gas_fees

st.title("One-Click Looping Calculator")

# Function to retrieve value from params or use default
def get_param_value(key, default, data_type):
    try:
        return data_type(params.get(key, [default])[0])
    except ValueError:  # Handle parsing issues
        return default
params = st.experimental_get_query_params()
default_collateral_token_name = "WMNT"
default_user_init_coll_amount = 100.
default_current_price_coll_token = 0.38
default_loan_token_name = "USDT"
default_current_price_loan_token = 1.
default_ltv = 0.9200
default_tenor = 7
default_apr = 0.1200
default_upfront_fee = 0.
default_myso_fee = 0.0008
default_dex_slippage = 0.0008
default_dex_swap_fee = 0.0005
default_gas_used = 1200000
default_gas_price = 20
default_eth_price = 0.3
default_expected_price_move_coll_token = 0.05

with st.sidebar:
    st.title("User Input")
    with st.expander("**Your Collateral Token**", expanded=True):
        collateral_token_name = st.text_input("Name of token you want to lever up", value=get_param_value("collateral_token_name", default_collateral_token_name, str))
        user_init_coll_amount = st.number_input("Amount of **{}** you want to lever up".format(collateral_token_name), min_value=0.1, max_value=100000000000.0, value=get_param_value("user_init_coll_amount", default_user_init_coll_amount, float))
        current_price_coll_token = st.number_input("Current **{}** Price in USD".format(collateral_token_name), value=get_param_value("current_price_coll_token", default_current_price_coll_token, float), format="%.4f")
        st.code(f"Value in USD: ${current_price_coll_token*user_init_coll_amount:,.2f}")

    with st.expander("**Your Loan Token**", expanded=False):
        loan_token_name = st.text_input("Name of token you want to borrow", value=get_param_value("loan_token_name", default_loan_token_name, str))
        current_price_loan_token = st.number_input("Current **{}** Price in USD".format(loan_token_name), value=get_param_value("current_price_loan_token", default_current_price_loan_token, float), format="%.4f")
        st.code(f"1 {collateral_token_name} = {current_price_coll_token/current_price_loan_token} {loan_token_name}")

    with st.expander("**Your Loan Terms**", expanded=True):
        ltv = st.number_input("LTV", min_value=0.01, max_value=1.0, value=get_param_value("ltv", default_ltv, float), format="%.4f")
        tenor = st.number_input("Tenor* (in days)", min_value=1, max_value=365, value=get_param_value("tenor", default_tenor, int))
        apr = st.number_input("APR", min_value=0.0, max_value=1.0, value=get_param_value("apr", default_apr, float), format="%.4f")
        upfront_fee = st.number_input("Upfront Fee", min_value=0.0, max_value=1.0, value=get_param_value("upfront_fee", default_upfront_fee, float), format="%.4f")
        myso_fee = st.number_input("MYSO Protocol Fee", min_value=0.0, value=get_param_value("myso_fee", default_myso_fee, float), max_value=1.0, format="%.4f")

    with st.expander("**Advanced: Input DEX Assumptions**"):
        dex_slippage = st.number_input("DEX Slippage", min_value=0.0, max_value=1.0, value=get_param_value("dex_slippage", default_dex_slippage, float), format="%.4f")
        dex_swap_fee = st.number_input("DEX Swap Fee", min_value=0.0, max_value=1.0, value=get_param_value("dex_swap_fee", default_dex_swap_fee, float), format="%.4f")

    with st.expander("**Advanced: Input Gas Price Assumptions**"):
        gas_used = st.number_input("Gas Used (full round trip)", min_value=0, max_value=100000000, value=get_param_value("gas_used", default_gas_used, int))
        gas_price = st.number_input("Gas Price (GWei)", min_value=0, max_value=100, value=get_param_value("gas_price", default_gas_price, int))
        eth_price = st.number_input("Gas Token Price (eg MNT price for Mantle)", min_value=0., max_value=10000., value=get_param_value("eth_price", default_eth_price, float))
        gas_usd_cost = gas_used * gas_price / 10**9 * eth_price
        st.code(f"Gas Cost in USD: ${gas_usd_cost:,.2f}")

    with st.expander("**Advanced: Share your input with this link**"):
        # Create a dictionary of all input values
        input_values = {
            "collateral_token_name": collateral_token_name,
            "user_init_coll_amount": user_init_coll_amount,
            "current_price_coll_token": current_price_coll_token,
            "loan_token_name": loan_token_name,
            "current_price_loan_token": current_price_loan_token,
            "ltv": ltv,
            "tenor": tenor,
            "apr": apr,
            "upfront_fee": upfront_fee,
            "myso_fee": myso_fee,
            "dex_slippage": dex_slippage,
            "dex_swap_fee": dex_swap_fee,
            "gas_used": gas_used,
            "gas_price": gas_price,
            "eth_price": eth_price
        }

        # Convert the dictionary to a query string
        query_string = "&".join([f"{key}={value}" for key, value in input_values.items()])

        base_url = "one-click-looping.streamlit.app/"  # Change this to your app's base URL
        shareable_link = base_url + "?" + query_string

        # Display the shareable link in a code block
        st.code(shareable_link)


flashloan_amount, owed_repayment, sold_on_dex, received_from_dex, combined_pledge, upfront_fee_abs, myso_fee_abs, final_pledge_and_reclaimable = calculate_open_position(
    current_price_coll_token, current_price_loan_token, user_init_coll_amount, ltv, apr, upfront_fee, tenor, myso_fee, dex_slippage, dex_swap_fee
)


def roi_function(price_multiplier):
    p1 = current_price_coll_token * price_multiplier
    p2 = current_price_loan_token
    _, _, _, final_amount_after_close2, _, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_cost)
    roi = final_amount_after_close2 * p2 / (current_price_coll_token * user_init_coll_amount) - 1
    return roi

def roi_minus_100_function(price_multiplier):
    p1 = current_price_coll_token / current_price_loan_token * price_multiplier
    p2 = current_price_loan_token
    _, _, _, final_amount_after_close2, _, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_cost)
    roi = final_amount_after_close2 * p2 / (current_price_coll_token * user_init_coll_amount) - 1
    return roi + 1  # Returns the difference between ROI and -100%


# Using fsolve to find the root of roi_minus_100_function
total_loss_multiplier = fsolve(roi_minus_100_function, 1.0)[0]
total_loss_price_change = (total_loss_multiplier - 1) * 100


st.write(f"""
    ### What is Looping?
    Looping via MYSO lets you leverage {collateral_token_name} against {loan_token_name} up to {final_pledge_and_reclaimable/user_init_coll_amount:,.2f}x, based on a {ltv*100:.1f}% LTV. Essentially, you're creating a leveraged call option position. Compared to perpetuals, there's no liquidation risk, meaning even if the {collateral_token_name}/{loan_token_name} price plummets and later rises, you capture the full upside. But beware, a price drop of {total_loss_price_change:.2f}% wipes out your {collateral_token_name} stake.
""")

st.write(f"""
### What Can I Earn With Looping?
Below you can see potential outcomes when looping with MYSO. Your RoI will depend on the realized price change of {collateral_token_name}/{loan_token_name} during the loan lifetime (currently assumed at {tenor} days, see LTV in loan terms input).
""")
# Use a range slider to define the range for hypothetical price changes
price_change_range = st.slider(
    f"**Define your expected price range for {collateral_token_name}/{loan_token_name} over the upcoming {tenor} days:**", 
    min_value=-100,  # you can adjust this lower limit based on your requirements
    max_value=100,   # you can adjust this upper limit based on your requirements
    value=(-2, 5)
)

rel_price_changes = []
RoIs = []

# Adjust the loop to take into account the user-defined range
for i in range(101):
    p1 = current_price_coll_token * (1 + (price_change_range[0] + (price_change_range[1] - price_change_range[0]) * i/100)/100)
    p2 = current_price_loan_token
    _, _, _, final_amount_after_close2, _, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_cost)
    rel_price_changes.append(p1/current_price_coll_token-1)
    RoIs.append(final_amount_after_close2 * p2 / (current_price_coll_token * user_init_coll_amount) - 1)

roi_unchanged = roi_function(1.0) * 100

break_even_multiplier = fsolve(roi_function, 1.0)[0]
break_even_price_change = (break_even_multiplier - 1) * 100

# Create and customize the plot
fig, ax = plt.subplots(figsize=(10, 5))
ax.axhline(y=0, color='black', linestyle='-', lw=.5)
ax.axvline(x=0, color='black', linestyle='-', lw=.5)
ax.plot([x*100 for x in rel_price_changes], [x*100 for x in RoIs], label=f'RoI Looping {collateral_token_name}', color='blue')
ax.plot([x*100 for x in rel_price_changes], [x*100 for x in rel_price_changes], label=f'RoI Buy&Hold {collateral_token_name}', linestyle='-', color='gray')
ax.fill_between([x*100 for x in rel_price_changes], [x*100 for x in RoIs], [0 for _ in rel_price_changes], where=[roi > 0 for roi, hold in zip(RoIs, rel_price_changes)], color='lightgreen', label='Profit')
ax.fill_between([x*100 for x in rel_price_changes], [x*100 for x in RoIs], [0 for _ in rel_price_changes], where=[roi <= 0 for roi, hold in zip(RoIs, rel_price_changes)], color='lightcoral', label='Loss')
if price_change_range[0] < break_even_price_change and break_even_price_change < price_change_range[1]:
    ax.axvline(x=break_even_price_change, color='green', lw=0.8, linestyle='--')
    ax.plot(break_even_price_change, 0, "o", color="green")
    # Annotate the break-even point below the x-axis
    tmp = f"+{break_even_price_change:.2f}" if break_even_price_change > 0 else f"{break_even_price_change:.2f}"
    ax.annotate(f'If price {tmp}%:\nBreak-even', 
                (break_even_price_change, min(RoIs)*100), 
                textcoords="offset points", 
                xytext=(0, -90),  # This offsets the annotation below the x-axis
                ha='center',
                va='top',  # This aligns the top of the text to the xytext
                arrowprops=dict(arrowstyle="->", linestyle='dotted', lw=0.8, color='green'))
if price_change_range[0] < total_loss_price_change and total_loss_price_change < price_change_range[1]:
    ax.axvline(x=total_loss_price_change, color='red', lw=0.8, linestyle='--')
    ax.plot(total_loss_price_change, -100, "o", color="red")
    # Annotate the full loss point below the x-axis
    tmp = f"+{total_loss_price_change:.2f}" if total_loss_price_change > 0 else f"{total_loss_price_change:.2f}"
    ax.annotate(f'If price {tmp}%:\nFull Loss', 
                (total_loss_price_change, min(RoIs)*100), 
                textcoords="offset points", 
                xytext=(0, -60),  # This offsets the annotation below the x-axis
                ha='center',
                va='top',  # This aligns the top of the text to the xytext
                arrowprops=dict(arrowstyle="->", linestyle='dotted', lw=0.8, color='red'))
# Annotation outside of the y-axis
tmp = f"+{roi_unchanged:.2f}" if roi_unchanged > 0 else f"{roi_unchanged:.2f}"
if price_change_range[0] < 0 and 0 < price_change_range[1]:   
    # Add vertical dotted line
    ax.axhline(y=roi_unchanged, color='orange', linestyle='--', lw=0.8)
    ax.plot(0, roi_unchanged, "o", color="orange")
    ax.annotate(f'If price flat:\n{tmp}% RoI',
                (price_change_range[0], roi_unchanged), 
                textcoords="offset points", 
                xytext=(-65, 0),  # This offsets the annotation to the left of the y-axis
                ha='right',
                va='center',  # This aligns the center of the text to the xytext
                arrowprops=dict(arrowstyle="->", linestyle='dotted', lw=0.8, color='orange'))
ax.grid(True, which='both', linestyle='--', linewidth=0.5)

ax.set_xlabel(f'Price Change of {collateral_token_name}/{loan_token_name} (%)')
ax.set_ylabel('RoI (%)')
ax.set_title(f'Your RoI for looping on {collateral_token_name}/{loan_token_name}')
ax.legend(loc="upper left")

st.pyplot(fig)


# List of predefined price changes
price_changes = [-5, -2, -1, 0, 1, 2, 3, 4, 5, 10, 15, 20]

# Compute RoIs for each price change
rois_for_changes = [(price, roi_function(1 + price/100) * 100) for price in price_changes]

df = pd.DataFrame(rois_for_changes, columns=["Price Change (%)", "Looping RoI (%)"])

# Expanded DataFrame to include price change bounds, break-even, flat scenario, and full loss
additional_points = [
    {"Price Change (%)": price_change_range[0], "Looping RoI (%)": roi_function(price_change_range[0]/100 + 1) * 100},
    {"Price Change (%)": price_change_range[1], "Looping RoI (%)": roi_function(price_change_range[1]/100 + 1) * 100},
    {"Price Change (%)": break_even_price_change, "Looping RoI (%)": 0},
    {"Price Change (%)": 0, "Looping RoI (%)": roi_unchanged},
    {"Price Change (%)": total_loss_price_change, "Looping RoI (%)": -100},
]
df = pd.concat([df, pd.DataFrame(additional_points)], ignore_index=True)
df.drop_duplicates(inplace=True)
df = df.sort_values(by="Price Change (%)", ascending=False)
# Reset the index for proper numbering
df.reset_index(drop=True, inplace=True)

def highlight_special_points(column):
    """
    Color the RoI cells based on their value and special points.
    """
    colors = []
    for val in column:
        if isinstance(val, str):  # Check if the value is a string
            value = float(val.rstrip('%'))
        else:
            value = val

        # For the "Price Change (%)" column, highlight additional points
        if column.name == "Price Change (%)":
            if value == round(break_even_price_change, 2) or value == 0 or value == round(total_loss_price_change, 2):
                colors.append('background-color: yellow')
            else:
                colors.append('')
        # For the "RoI (%)" column, highlight positive RoI in green and negative RoI in red
        elif column.name == "Looping RoI (%)":
            if value >= 0:
                colors.append('background-color: lightgreen')
            elif value < 0:
                colors.append('background-color: lightcoral')
            else:
                colors.append('')
        else:
            colors.append('')  # Default - no highlighting
    return colors

# Format the values for better display
df["Price Change (%)"] = df["Price Change (%)"].apply(lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%")
df["Looping RoI (%)"] = df["Looping RoI (%)"].apply(lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%")


st.write(f"""Above, you can view the RoI from looping (blue curve) based on different {collateral_token_name}/{loan_token_name} price changes. You can also see how it compares to simply holding {collateral_token_name} (gray curve). Below, a table provides a detailed view on some of the points.""")

# If you still want to display the full DataFrame below the selected row
styled_df = df.style.apply(highlight_special_points)
st.table(styled_df)
st.write(f"""
    There are 3 important scenarios to be aware of (yellow shaded cells):
    
    - **Break-even**: The price of {collateral_token_name}/{loan_token_name} needs to move by at least {"+" if break_even_price_change > 0 else ""}{break_even_price_change:.2f}% for you to break even.

    - **Unwinding Immediately**: If the price of {collateral_token_name}/{loan_token_name} stays flat, or if you decide to unwind your position immediately, your RoI will be {roi_unchanged:.2f}%.

    - **Total Loss**: A drop to {total_loss_price_change:.2f}% in the price of {collateral_token_name}/{loan_token_name} will result in a complete loss.
    """)

st.write(f"""### How Does Looping Work?""")
st.write(f"""
Looping with MYSO enables users to create a leveraged position, amplifying the potential returns of their base assets. Below you can see the individual steps involved in the looping process, illuminating what occurs behind the scenes. 

Enter your expected price appreciation for {collateral_token_name} compared to {loan_token_name} over the loan duration of {tenor} days below. You'll receive a detailed breakdown tailored to that specific price scenario.""")

expected_price_move_coll_token = st.number_input(f"**Expected {collateral_token_name}/{loan_token_name} price change (in next {tenor} days):**", min_value=-1.0, max_value=10.0, value=get_param_value("expected_price_move_coll_token", default_expected_price_move_coll_token, float), format="%.4f")

final_price_coll_token = current_price_coll_token * (1 + expected_price_move_coll_token)
final_price_loan_token = current_price_loan_token


flashloan_amount2, sold_on_dex2, received_from_dex2, final_amount_after_close2, rational_to_repay, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, final_price_coll_token, final_price_loan_token, dex_slippage, dex_swap_fee, gas_usd_cost)

roi = final_amount_after_close2 * final_price_loan_token / (current_price_coll_token * user_init_coll_amount) - 1







# Add subheaders for clarity
subheaders = [
    "Initial Position",
    "Flashborrow and DEX",
    "Collateralization and Fees",
    "Close Position"
]

# Create data with the new structure
data = {
    'Description': [
        f'Your initial {collateral_token_name} position',
        f'{loan_token_name} Flashborrow to open', 
        f"{loan_token_name} sold on DEX",
        f"{collateral_token_name} received from DEX",
        f'Your total {collateral_token_name} position',
        f'Fees to MYSO (Upfront and Protocol)',
        'Final Pledged Amount',
        'Leverage',
        f"{collateral_token_name} Flashborrow to close",
        f"{collateral_token_name} sold on DEX",
        f"{loan_token_name} received from DEX",
        f"Repayment of {loan_token_name}",
        f"Remaining {loan_token_name} after Repayment",
        f"Final RoI",
        f"Gas costs",
        f"Final RoI (net gas costs)",
    ],
    'Open Position Amount': [
        f"{user_init_coll_amount:,.2f} {collateral_token_name} (${user_init_coll_amount*current_price_coll_token:,.2f})",
        f"+{flashloan_amount:,.2f} {loan_token_name} (${flashloan_amount*current_price_loan_token:,.2f})", 
        f"-{sold_on_dex:,.2f} {loan_token_name} (${sold_on_dex*current_price_loan_token:,.2f})",
        f"+{received_from_dex:,.2f} {collateral_token_name} (${received_from_dex*current_price_coll_token:,.2f})",
        f"-{combined_pledge:,.2f} {collateral_token_name} (${combined_pledge*current_price_coll_token:,.2f})",
        f"-{upfront_fee_abs + myso_fee_abs:,.2f} {collateral_token_name} (${(upfront_fee_abs + myso_fee_abs)*current_price_coll_token:,.2f})",
        f"+{final_pledge_and_reclaimable:,.2f} {collateral_token_name} (${final_pledge_and_reclaimable*current_price_coll_token:,.2f})",
        f"{final_pledge_and_reclaimable/user_init_coll_amount:,.2f}x",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-"
    ],
    'Close Position Amount': [
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        f"+{flashloan_amount2:,.2f} {collateral_token_name} (${flashloan_amount2*current_price_coll_token:,.2f})",
        f"-{sold_on_dex2:,.2f} {collateral_token_name} (${sold_on_dex2*current_price_coll_token:,.2f})",
        f"+{received_from_dex2:,.2f} {loan_token_name} (${received_from_dex2*current_price_loan_token:,.2f})",
        f"-{owed_repayment:,.2f} {loan_token_name} (${owed_repayment*current_price_loan_token:,.2f})",
        f"+{final_amount_after_close2:,.2f} {loan_token_name} (${final_amount_after_close2*current_price_loan_token:,.2f})",
        f"{final_amount_after_close2*current_price_loan_token/(user_init_coll_amount*current_price_coll_token)*100-100:,.2f}%",
        f"-${gas_usd_cost:,.2f}",
        f"{(final_amount_after_close2*current_price_loan_token-gas_usd_cost)/(user_init_coll_amount*current_price_coll_token)*100-100:,.2f}%"
    ]
}

# Display the table in Streamlit
st.table(data)


st.write(f"""
**Summary:**
- **Initial Position:** You start with a position of {user_init_coll_amount:,.2f} {collateral_token_name}, valued at ${user_init_coll_amount*current_price_coll_token:,.2f}.
  
- **Opening Leveraged Position:** Through looping, you leverage this position to {final_pledge_and_reclaimable/user_init_coll_amount:,.2f}x its original size.

- **Unwinding Position:** If the price change unfolds as anticipated, it would be rational for you to {f"repay and unwind your looping position, given that your {collateral_token_name} leveraged collateral exceeds your {loan_token_name} debt" if final_amount_after_close2 > 0 else f"default and let your looping position expire, as your {collateral_token_name} leveraged collateral is valued less than your {loan_token_name} debt owed"}.

- **Final Position:** Consequently, your end position would be {final_amount_after_close2:,.2f} {loan_token_name} (equivalent to ${final_amount_after_close2*final_price_loan_token:,.2f}), yielding an RoI of {final_amount_after_close2*final_price_loan_token/(user_init_coll_amount*current_price_coll_token)*100-100:,.2f}%.
""")


# Values for the bar chart
labels = [
    f'Your Initial {collateral_token_name}\n (Inception)', 
    f'Flasborrowed {loan_token_name}\n (Inception)',
    f'Leveraged {collateral_token_name}\n (Open Position)', 
    f'{loan_token_name} Owed\n (Open Position)', 
    f'Flashborrowed {collateral_token_name}\n (Close Position)',
    f'{loan_token_name} Owed\n (Close Position)',
    f'Your Final {loan_token_name}\n (Final Position)'
]

values = [
    user_init_coll_amount * current_price_coll_token,
    flashloan_amount * current_price_loan_token,
    combined_pledge * current_price_coll_token,
    owed_repayment * current_price_loan_token,
    combined_pledge * final_price_coll_token,
    owed_repayment * final_price_loan_token,
    final_amount_after_close2 * final_price_loan_token
]

amounts = [
    user_init_coll_amount,
    flashloan_amount,
    combined_pledge,
    owed_repayment,
    flashloan_amount2,
    owed_repayment,
    final_amount_after_close2
]

tokens = [
    collateral_token_name,
    loan_token_name,
    collateral_token_name,
    loan_token_name,
    collateral_token_name,
    loan_token_name,
    loan_token_name
]

colors = ['gray', 'gray', 'green', 'red', 'green', 'red', 'blue']

# Create the bar chart
fig, ax = plt.subplots(figsize=(12, 7))
bars = ax.bar(labels, values, color=colors)

# Add annotations to the bars
for i, rect in enumerate(bars):
    height = rect.get_height()
    ax.text(rect.get_x() + rect.get_width()/2., 1.05 * height,
            f"${values[i]:,.2f}\n({amounts[i]:,.2f} {tokens[i]})", ha='center', va='bottom', rotation=0)

    # Adding vertical lines after every two bars
    if (i+1) % 2 == 0 and i != len(bars) - 1:  # Check that it's not the last bar
        ax.axvline(x=rect.get_x() + rect.get_width() + 0.1, color='black', linestyle='--')

# Highlight the negative values with a different color
for i, v in enumerate(values):
    if v < 0:
        bars[i].set_color('red')

ax.set_title("Overview of Assets vs Debts, pre and post Looping")
ax.set_ylabel('Amount (USD)')
locations = ax.get_xticks()  # Assuming you want to set labels for existing tick locations
ax.xaxis.set_major_locator(plt.FixedLocator(locations))
ax.set_xticklabels(labels, rotation=45, ha='right')
ax.set_ylim(0, max(values)*1.2)  # Add some space at the top for annotations

# Display the bar chart in Streamlit
st.pyplot(fig)


st.write(f"""Note: You can share the calculated scenario using this link""")
input_values = {
    "collateral_token_name": collateral_token_name,
    "user_init_coll_amount": user_init_coll_amount,
    "current_price_coll_token": current_price_coll_token,
    "loan_token_name": loan_token_name,
    "current_price_loan_token": current_price_loan_token,
    "ltv": ltv,
    "tenor": tenor,
    "apr": apr,
    "upfront_fee": upfront_fee,
    "myso_fee": myso_fee,
    "dex_slippage": dex_slippage,
    "dex_swap_fee": dex_swap_fee,
    "gas_used": gas_used,
    "gas_price": gas_price,
    "eth_price": eth_price,
    "expected_price_move_coll_token": expected_price_move_coll_token
}

# Convert the dictionary to a query string
query_string2 = "&".join([f"{key}={value}" for key, value in input_values.items()])
shareable_link2 = base_url + "?" + query_string2

# Display the shareable link in a code block
st.code(shareable_link2)
