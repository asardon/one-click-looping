import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from scipy.optimize import bisect, minimize
from urllib.parse import urlencode

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

def calculate_close_position(final_pledge_and_reclaimable, owed_repayment, final_price_coll_token, final_price_loan_token, dex_slippage, dex_swap_fee, gas_usd_cost, always_repay=False):
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
    rational_to_repay = always_repay if always_repay else final_amount_after_close > 0

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
params = params if params is not None else {}
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
default_price_move_from = -5.
default_price_move_to = 10.
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

flashloan_amount, owed_repayment, sold_on_dex, received_from_dex, combined_pledge, upfront_fee_abs, myso_fee_abs, final_pledge_and_reclaimable = calculate_open_position(
    current_price_coll_token, current_price_loan_token, user_init_coll_amount, ltv, apr, upfront_fee, tenor, myso_fee, dex_slippage, dex_swap_fee
)

def calc_roi(final_loan_token_amount_after_close, final_loan_token_price, user_init_coll_amount, init_coll_token_price):
    return final_loan_token_amount_after_close * final_loan_token_price / (user_init_coll_amount * init_coll_token_price) - 1

def calc_roi2(coll_usd_price_change, target_roi, current_price_coll_token, current_price_loan_token, final_pledge_and_reclaimable, owed_repayment, dex_slippage, dex_swap_fee, gas_usd_cost):
    p1 = current_price_coll_token * (1 + coll_usd_price_change)
    p2 = current_price_loan_token
    _, _, _, final_amount_after_close2, _, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_cost, True)
    roi = calc_roi(final_amount_after_close2, p2, user_init_coll_amount, current_price_coll_token)
    return roi - target_roi

total_loss_price_change = bisect(calc_roi2, -1., 2., args=(-1., current_price_coll_token, current_price_loan_token, final_pledge_and_reclaimable, owed_repayment, dex_slippage, dex_swap_fee, gas_usd_cost)) * 100

st.write(f"""
### What is One-Click Looping?
With MYSO's one-click looping, you can create a leveraged position in {collateral_token_name} against {loan_token_name} up to a ratio of {final_pledge_and_reclaimable/user_init_coll_amount:,.2f}x (assuming {ltv*100:.1f}% LTV). Instead of consecutively pledging {collateral_token_name} to borrow {loan_token_name}, swapping it for {collateral_token_name}, and repeating the process, one-click looping lets you handle all these steps in one efficient transaction.\n\nAnd unlike perpetuals, there's no risk of liquidation. This ensures that even if the price of {collateral_token_name}/{loan_token_name} plummets, you maintain the full upside potential if the price rebounds again. However, exercise caution: if the price of {collateral_token_name}/{loan_token_name} decreases and remains below {total_loss_price_change:.2f}% for the entire loan duration, your leveraged {collateral_token_name} position will be worth less than the debt you owe. As a result, you won't be able to recover your position without additional {loan_token_name} capital and could suffer a total, 100% loss.
""")

st.write(f"""
### What Can I Earn With Looping?
Below you can see potential outcomes when looping with MYSO. Your RoI will depend on the realized price change of {collateral_token_name}/{loan_token_name} during the loan lifetime.
""")
# Use a range slider to define the range for hypothetical price changes
price_change_range = st.slider(
    f"**Define your expected from/to price range for {collateral_token_name}/{loan_token_name} over the upcoming {tenor} days:**", 
    min_value=-100.,  # you can adjust this lower limit based on your requirements
    max_value=100.,   # you can adjust this upper limit based on your requirements
    value=(get_param_value("price_move_from", default_price_move_from, float), get_param_value("price_move_to", default_price_move_to, float)),
    format="%.0f%%"  # Added the % sign after the float format
)

rel_price_changes = []
RoIs = []
rois_for_changes = []

# Adjust the loop to take into account the user-defined range
for i in range(101):
    p1 = current_price_coll_token * (1 + (price_change_range[0] + (price_change_range[1] - price_change_range[0]) * i/100)/100)
    p2 = current_price_loan_token
    _, _, _, final_amount_after_close2, _, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_cost)
    rel_price_changes.append(p1/current_price_coll_token-1)
    roi = calc_roi(final_amount_after_close2, p2, user_init_coll_amount, current_price_coll_token)
    RoIs.append(roi)
    if i % 10 == 0:
        rois_for_changes.append(((p1/current_price_coll_token-1)*100, roi*100))

_, _, _, final_amount_after_close3, _, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, current_price_coll_token, current_price_loan_token, dex_slippage, dex_swap_fee, gas_usd_cost)
roi_unchanged = calc_roi(final_amount_after_close3, current_price_loan_token, user_init_coll_amount, current_price_coll_token) * 100

break_even_price_change = bisect(calc_roi2, -1., 2., args=(.0, current_price_coll_token, current_price_loan_token, final_pledge_and_reclaimable, owed_repayment, dex_slippage, dex_swap_fee, gas_usd_cost)) * 100

# Create and customize the plot
fig, ax = plt.subplots(figsize=(10, 5))
ax.axhline(y=0, color='black', linestyle='-', lw=.5)
ax.axvline(x=0, color='black', linestyle='-', lw=.5)
ax.plot([x*100 for x in rel_price_changes], [x*100 for x in RoIs], label=f'RoI Looping {collateral_token_name}', color='deepskyblue')
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
                color="green",
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
                color="red",
                xytext=(0, -60),  # This offsets the annotation below the x-axis
                ha='center',
                va='top',  # This aligns the top of the text to the xytext
                arrowprops=dict(arrowstyle="->", linestyle='dotted', lw=0.8, color='red'))
# Annotation outside of the y-axis
tmp = f"+{roi_unchanged:.2f}" if roi_unchanged > 0 else f"{roi_unchanged:.2f}"
if price_change_range[0] < 0 and 0 < price_change_range[1]:   
    # Add vertical dotted line
    ax.axhline(y=roi_unchanged, color='darkblue', linestyle='--', lw=0.8)
    ax.plot(0, roi_unchanged, "o", color="darkblue")
    ax.annotate(f'If price flat:\n{tmp}% RoI',
                (price_change_range[0], roi_unchanged), 
                textcoords="offset points", 
                color="darkblue",
                xytext=(-65, 0),  # This offsets the annotation to the left of the y-axis
                ha='right',
                va='center',  # This aligns the center of the text to the xytext
                arrowprops=dict(arrowstyle="->", linestyle='dotted', lw=0.8, color='darkblue'))
ax.grid(True, which='both', linestyle='--', linewidth=0.5)

ax.set_xlabel(f'Price Change of {collateral_token_name}/{loan_token_name} (%)')
ax.set_ylabel('RoI (%)')
ax.set_title(f'Your RoI for looping on {collateral_token_name}/{loan_token_name}')
ax.legend(loc="upper left")

st.pyplot(fig)


# add special points
p1 = current_price_coll_token
p2 = current_price_loan_token
_, _, _, final_amount_after_close2, _, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_cost)
rel_price_changes.append(p1/current_price_coll_token-1)
roi = calc_roi(final_amount_after_close2, p2, user_init_coll_amount, current_price_coll_token)
rois_for_changes.append(((p1/current_price_coll_token-1)*100, roi*100))

p1 = current_price_coll_token * (1 + break_even_price_change/100)
p2 = current_price_loan_token
_, _, _, final_amount_after_close2, _, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_cost)
rel_price_changes.append(p1/current_price_coll_token-1)
roi = calc_roi(final_amount_after_close2, p2, user_init_coll_amount, current_price_coll_token)
rois_for_changes.append(((p1/current_price_coll_token-1)*100, roi*100))

p1 = current_price_coll_token * (1 + total_loss_price_change/100)
p2 = current_price_loan_token
_, _, _, final_amount_after_close2, _, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_cost)
rel_price_changes.append(p1/current_price_coll_token-1)
roi = calc_roi(final_amount_after_close2, p2, user_init_coll_amount, current_price_coll_token)
rois_for_changes.append(((p1/current_price_coll_token-1)*100, roi*100))

df = pd.DataFrame(rois_for_changes, columns=["Price Change (%)", "Looping RoI (%)"])
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
                colors.append('background-color: lightgray; color: black')
            else:
                colors.append('')
        # For the "RoI (%)" column, highlight positive RoI in green and negative RoI in red
        elif column.name == "Looping RoI (%)":
            if value >= 0:
                colors.append('background-color: lightgreen; color: black')
            elif value < 0:
                colors.append('background-color: lightcoral; color: black')
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
    There are 3 important scenarios to be aware of (gray shaded rows):
    
    - **Break-even**: The price of {collateral_token_name}/{loan_token_name} needs to move by at least {"+" if break_even_price_change > 0 else ""}{break_even_price_change:.2f}% for you to break even.

    - **Unwinding Immediately**: If the price of {collateral_token_name}/{loan_token_name} stays flat, or if you decide to unwind your position immediately, your RoI will be {roi_unchanged:.2f}%.

    - **Total Loss**: If the price of {collateral_token_name}/{loan_token_name} drops and stays below {total_loss_price_change:.2f}% throughout the entire loan duration, your leveraged {collateral_token_name} collateral will be worth less than your {loan_token_name} debt. In this situation, it would be rational for you to not repay, in which case you'll suffer a 100% loss.
    """)

st.write(f"""### How Does Looping Work?""")
st.write(f"""
For a more detailed scenario breakdown, you can input the {collateral_token_name}/{loan_token_name} price change you expect over the loan duration of {tenor} days.""")

expected_price_move_coll_token = st.number_input(f"**Expected {collateral_token_name}/{loan_token_name} price change:**", min_value=-1.0, max_value=10.0, value=get_param_value("expected_price_move_coll_token", default_expected_price_move_coll_token, float), format="%.4f")

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
        f'Your Initial {collateral_token_name} Position',
        f'{loan_token_name} Flashborrow to Open', 
        f"{loan_token_name} Sold on DEX",
        f"{collateral_token_name} Received from DEX",
        f'Your Total {collateral_token_name} Position',
        f'Upfront Fee to Lender',
        f'MYSO Protocol Fee',
        'Final Pledged Amount',
        'Leverage',
        f"{collateral_token_name} Flashborrow To Close",
        f"{collateral_token_name} Sold on DEX",
        f"{loan_token_name} Received from DEX",
        f"Repayment of {loan_token_name}",
        f"Remaining {loan_token_name} after Repayment",
        f"Final RoI",
        f"Gas Costs",
        f"Final RoI (net gas costs)",
    ],
    'Open Position Amount': [
        f"{user_init_coll_amount:,.4f} {collateral_token_name} (${user_init_coll_amount*current_price_coll_token:,.2f})",
        f"+{flashloan_amount:,.4f} {loan_token_name} (${flashloan_amount*current_price_loan_token:,.2f})", 
        f"-{sold_on_dex:,.4f} {loan_token_name} (${sold_on_dex*current_price_loan_token:,.2f})",
        f"+{received_from_dex:,.4f} {collateral_token_name} (${received_from_dex*current_price_coll_token:,.2f})",
        f"-{combined_pledge:,.4f} {collateral_token_name} (${combined_pledge*current_price_coll_token:,.2f})",
        f"-{upfront_fee_abs:,.4f} {collateral_token_name} (${(upfront_fee_abs)*current_price_coll_token:,.2f})",
        f"-{myso_fee_abs:,.4f} {collateral_token_name} (${(myso_fee_abs)*current_price_coll_token:,.2f})",
        f"+{final_pledge_and_reclaimable:,.4f} {collateral_token_name} (${final_pledge_and_reclaimable*current_price_coll_token:,.2f})",
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
        "-",
        f"+{flashloan_amount2:,.4f} {collateral_token_name} (${flashloan_amount2*current_price_coll_token:,.2f})",
        f"-{sold_on_dex2:,.4f} {collateral_token_name} (${sold_on_dex2*current_price_coll_token:,.2f})",
        f"+{received_from_dex2:,.4f} {loan_token_name} (${received_from_dex2*current_price_loan_token:,.2f})",
        f"-{owed_repayment:,.4f} {loan_token_name} (${owed_repayment*current_price_loan_token:,.2f})",
        f"+{final_amount_after_close2:,.4f} {loan_token_name} (${final_amount_after_close2*current_price_loan_token:,.2f})",
        f"{final_amount_after_close2*current_price_loan_token/(user_init_coll_amount*current_price_coll_token)*100-100:,.2f}% ({(final_amount_after_close2*current_price_loan_token/(user_init_coll_amount*current_price_coll_token)*100-100)*365/tenor:,.2f}% p.a.)",
        f"-${gas_usd_cost:,.2f}",
        f"{(final_amount_after_close2*current_price_loan_token-gas_usd_cost)/(user_init_coll_amount*current_price_coll_token)*100-100:,.2f}% ({((final_amount_after_close2*current_price_loan_token-gas_usd_cost)/(user_init_coll_amount*current_price_coll_token)*100-100)*365/tenor:,.2f}% p.a.)"
    ]
}

# Display the table in Streamlit
st.table(data)


st.write(f"""
**Summary:**
- **Initial Position:** You start with a position of {user_init_coll_amount:,.2f} {collateral_token_name}, valued at ${user_init_coll_amount*current_price_coll_token:,.2f}.
  
- **Opening Leveraged Position:** Through looping, you leverage this position to {final_pledge_and_reclaimable/user_init_coll_amount:,.2f}x its original size.

- **Unwinding Position:** If the price change unfolds as anticipated, it would be rational for you to {f"repay and unwind your looping position, given that your {collateral_token_name} leveraged collateral is worth more than your {loan_token_name} debt" if final_amount_after_close2 > 0 else f"default and let your looping position expire without repaying, as your {collateral_token_name} leveraged collateral is worth less than your {loan_token_name} debt"}.

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

colors = ['lightgray', 'lightgray', 'lightgreen', 'lightcoral', 'lightgreen', 'lightcoral', 'lightblue']

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


st.write(f"""💡You can share the calculated scenario using this link:""")
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
    "price_move_from": price_change_range[0],
    "price_move_to": price_change_range[1],
    "expected_price_move_coll_token": expected_price_move_coll_token
}

# Convert the dictionary to a query string
base_url = "one-click-looping.streamlit.app/"  # Change this to your app's base URL
query_string = urlencode(input_values)
shareable_link = base_url + "?" + query_string

# Display the shareable link in a code block
st.code(shareable_link)
