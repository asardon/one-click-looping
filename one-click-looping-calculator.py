import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import fsolve

def calculate_open_position(current_price_coll_token, current_price_loan_token, user_init_coll_amount, ltv, apr, upfront_fee, tenor, myso_fee, dex_slippage, dex_swap_fee):
    cross_price = current_price_coll_token / current_price_loan_token
    
    # Calculate flashloan amount
    flashloan_amount = user_init_coll_amount * cross_price / (1 - ltv)

    # Calculate owed repayment amount
    owed_repayment = flashloan_amount * (1 + apr * tenor/365)

    # Amount that's sold on the DEX 
    sold_on_dex = flashloan_amount

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
    return flashloan_amount, owed_repayment, sold_on_dex, received_from_dex, combined_pledge, upfront_fee_abs, myso_fee_abs, final_pledge_and_reclaimable

def calculate_close_position(final_pledge_and_reclaimable, owed_repayment, final_price_coll_token, final_price_loan_token, dex_slippage, dex_swap_fee, gas_usd_price):
    cross_price = final_price_coll_token / final_price_loan_token
    
    # Amount flashborrowed
    flashloan_amount = final_pledge_and_reclaimable

    # Amount that's sold on the DEX 
    sold_on_dex = flashloan_amount

    # Amount received from the DEX (after considering slippage and swap fee)
    received_from_dex = sold_on_dex * cross_price * (1 - dex_slippage - dex_swap_fee)

    # Amount left over after repay
    final_amount_after_close = received_from_dex - owed_repayment - gas_usd_price

    # Myso protocol fee
    rational_to_repay = final_amount_after_close > 0

    if not rational_to_repay:
        flashloan_amount = 0 
        sold_on_dex = 0
        received_from_dex = 0
        final_amount_after_close = 0
    
    # Return results
    return flashloan_amount, sold_on_dex, received_from_dex, final_amount_after_close, rational_to_repay

st.title("One-Click Looping Calculator")

with st.sidebar:
    st.header("General Token Info")
    collateral_token_name = st.text_input("Collateral Token Name", value="WMNT")
    current_price_coll_token = st.number_input("Current Collateral Token Price in USD", value=0.38, format="%.4f")
    loan_token_name = st.text_input("Loan Token Name", value="USDT")
    current_price_loan_token = st.number_input("Current Loan Token Price in USD", value=1.0, format="%.4f")
    st.code(f"1 {collateral_token_name} = {current_price_coll_token/current_price_loan_token} {loan_token_name}")

    st.header(f"Your Token Info")
    user_init_coll_amount = st.number_input("Amount of {} you hold and want to go leveraged long".format(collateral_token_name), min_value=0.1, max_value=100000000000.0, value=380.)
    st.code(f"Value in USD: ${current_price_coll_token*user_init_coll_amount:,.2f}")

    st.header("Your Market View")
    expected_price_move_coll_token = st.number_input(f"Input {collateral_token_name} price change you expect during loan tenor*", min_value=-1.0, max_value=10.0, value=0.05)
    expected_price_move_loan_token = st.number_input(f"Input {loan_token_name} price change you expect during loan tenor*", min_value=-1.0, max_value=10.0, value=0.0)

    st.header("Loan Parameters")
    ltv = st.number_input("LTV", min_value=0.01, max_value=1.0, value=0.8)
    tenor = st.number_input("Tenor* (in days)", min_value=1, max_value=365, value=5)
    apr = st.number_input("APR", min_value=0.0, max_value=1.0, value=0.05)
    upfront_fee = st.number_input("Upfront Fee", min_value=0.0, max_value=1.0, value=0.0, format="%.4f")
    myso_fee = st.number_input("MYSO Protocol Fee", min_value=0.0, value=0.002, max_value=1.0, format="%.4f")

    st.header("DEX Assumptions")
    dex_slippage = st.number_input("DEX Slippage", min_value=0.0, max_value=1.0, value=0.005, format="%.4f")
    dex_swap_fee = st.number_input("DEX Swap Fee", min_value=0.0, max_value=1.0, value=0.0025, format="%.4f")

    st.header("Gas Price Assumptions")
    gas_used = st.number_input("Gas Used (full round trip)", min_value=0, max_value=100000000, value=1200000)
    gas_price = st.number_input("Gas Price (GWei)", min_value=0, max_value=100, value=20)
    eth_price = st.number_input("ETH Price (or other L2 Price)", min_value=0., max_value=10000., value=0.3)
    gas_usd_price = gas_used * gas_price / 10**9 * eth_price
    st.code(f"Gas Cost in USD: ${gas_usd_price:,.2f}")

final_price_coll_token = current_price_coll_token * (1 + expected_price_move_coll_token)
final_price_loan_token = current_price_loan_token * (1 + expected_price_move_loan_token)

flashloan_amount, owed_repayment, sold_on_dex, received_from_dex, combined_pledge, upfront_fee_abs, myso_fee_abs, final_pledge_and_reclaimable = calculate_open_position(
    current_price_coll_token, current_price_loan_token, user_init_coll_amount, ltv, apr, upfront_fee, tenor, myso_fee, dex_slippage, dex_swap_fee
)

# Sliders for user input on the range of price changes
min_price_change_percent = st.slider(
    f'Set the min range for hypothetical {collateral_token_name}/{loan_token_name} price changes (%):', 
    min_value=-100,  # you can adjust this lower limit based on your requirements
    max_value=0, 
    value=-100  # default value
)

max_price_change_percent = st.slider(
    f'Set the max range for {collateral_token_name}/{loan_token_name} price changes (%):', 
    min_value=min_price_change_percent,  # Ensures max is always >= min
    max_value=200,  # you can adjust this upper limit based on your requirements
    value=100  # default value
)

rel_price_changes = []
RoIs = []

# Adjust the loop to take into account the user-defined range
for i in range(101):
    p1 = current_price_coll_token * (1 + (min_price_change_percent + (max_price_change_percent - min_price_change_percent) * i/100)/100)
    p2 = current_price_loan_token
    _, _, _, final_amount_after_close2, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_price)
    rel_price_changes.append(p1/current_price_coll_token-1)
    RoIs.append(final_amount_after_close2 * p2 / (current_price_coll_token * user_init_coll_amount) - 1)

def roi_function(price_multiplier):
    p1 = current_price_coll_token / current_price_loan_token * price_multiplier
    p2 = current_price_loan_token
    _, _, _, final_amount_after_close2, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_price)
    roi = final_amount_after_close2 * p2 / (current_price_coll_token * user_init_coll_amount) - 1
    return roi

# Use fsolve to find the root of the roi_function
break_even_multiplier = fsolve(roi_function, 1.0)[0]
break_even_price_change = (break_even_multiplier - 1) * 100


# Create the figure and axes
fig, ax = plt.subplots(figsize=(10, 5))

# Plot the RoI based on price changes
ax.plot([x*100 for x in rel_price_changes], [x*100 for x in RoIs], label=f'RoI Looping {collateral_token_name}', color='blue')

# Plot the RoI for simply holding the collateral
ax.plot([x*100 for x in rel_price_changes], [x*100 for x in rel_price_changes], label=f'RoI Hold {collateral_token_name}', linestyle='--', color='red')

# Fill the profit zone (looping > holding)
ax.fill_between([x*100 for x in rel_price_changes], [x*100 for x in RoIs], [x*100 for x in rel_price_changes], where=[roi > hold for roi, hold in zip(RoIs, rel_price_changes)], color='lightgreen', label='Looping Outperformance Zone')

# Fill the loss zone (looping < holding)
ax.fill_between([x*100 for x in rel_price_changes], [x*100 for x in RoIs], [x*100 for x in rel_price_changes], where=[roi <= hold for roi, hold in zip(RoIs, rel_price_changes)], color='lightcoral', label='Loss Zone')

# Add a vertical line for the break-even point
ax.axvline(x=break_even_price_change, color='green', linestyle='--')
ax.annotate(f'Break-even\n{break_even_price_change:.2f}%', (break_even_price_change, 0), textcoords="offset points", xytext=(-10,10), ha='center')

# Setting labels and title
ax.set_xlabel(f'Price Change of {collateral_token_name}/{loan_token_name} (%)')
ax.set_ylabel('RoI (%)')
ax.set_title(f'Looping RoI based on {collateral_token_name}/{loan_token_name} price changes')
ax.legend(loc="upper left")

# Display the plot in Streamlit
st.pyplot(fig)


flashloan_amount2, sold_on_dex2, received_from_dex2, final_amount_after_close2, rational_to_repay = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, final_price_coll_token, final_price_loan_token, dex_slippage, dex_swap_fee, gas_usd_price)

roi = final_amount_after_close2 / (current_price_coll_token * user_init_coll_amount) - 1

st.markdown(f"### **Summary**")
st.text(f"Initial Position: {user_init_coll_amount:,.2f} {collateral_token_name} (${user_init_coll_amount*current_price_coll_token:,.2f})")
st.text(f"Leverage: {final_pledge_and_reclaimable/user_init_coll_amount:,.2f}x")
st.text(f"Break even price change: {break_even_price_change:,.2f}%")
st.text(f"Assumed {collateral_token_name}/{loan_token_name} price change: {final_price_coll_token/current_price_coll_token/(final_price_loan_token/current_price_loan_token)*100-100:,.2f}%")
st.text(f"Resulting Closing Position: {final_amount_after_close2:,.2f} {loan_token_name} (${final_amount_after_close2*final_price_loan_token:,.2f})")
st.text(f"Resulting RoI: {100*final_amount_after_close2*final_price_loan_token/(user_init_coll_amount*current_price_coll_token)-100:,.2f}%")



# Values for the bar chart
labels = [
    'Initial Collateral Value', 
    'Leveraged Collateral (Open)', 
    'Repayment Owed (Open)', 
    'Leveraged Collateral Value (Close)',
    'Repayment Owed (Close)',
    'Final Remainder'
]

values = [
    current_price_coll_token * user_init_coll_amount,
    combined_pledge * current_price_coll_token,
    owed_repayment * current_price_loan_token,
    combined_pledge * final_price_coll_token,
    owed_repayment * final_price_loan_token,
    final_amount_after_close2 * final_price_loan_token
]

amounts = [
    user_init_coll_amount,
    combined_pledge,
    owed_repayment,
    flashloan_amount2,
    owed_repayment,
    final_amount_after_close2
]

tokens = [
    collateral_token_name,
    collateral_token_name,
    loan_token_name,
    collateral_token_name,
    loan_token_name,
    loan_token_name
]

colors = ['gray', 'green', 'red', 'green', 'red', 'blue']

# Create the bar chart
fig, ax = plt.subplots(figsize=(12, 7))
bars = ax.bar(labels, values, color=colors)

# Add annotations to the bars
for i, rect in enumerate(bars):
    height = rect.get_height()
    ax.text(rect.get_x() + rect.get_width()/2., 1.05 * height,
            f"${values[i]:,.2f}\n({amounts[i]:,.2f} {tokens[i]})", ha='center', va='bottom', rotation=0)

# Highlight the negative values with a different color
for i, v in enumerate(values):
    if v < 0:
        bars[i].set_color('red')

ax.set_title("Overview of Assets vs Debts, pre and post Looping")
ax.set_ylabel('Amount (USD)')
ax.set_xticklabels(labels, rotation=45, ha='right')
ax.set_ylim(0, max(values)*1.2)  # Add some space at the top for annotations

# Display the bar chart in Streamlit
st.pyplot(fig)


st.markdown(f"### **Details: Open Looping Position**")
open_position_data = {
    'Description': [
        "Flashborrow from MYSO Lender", 
        "Owed Repayment to MYSO Lender", 
        "Interest Owed to MYSO Lender", 
        "Sell on DEX", 
        "Receive from DEX", 
        "Combined Pledge to MYSO Lender", 
        "Upfront Fee to MYSO Lender", 
        "Fee to MYSO Protocol", 
        "Combined Pledge to MYSO Lender (net of fees)",
        "Leverage"
    ],
    'Amount': [
        f"{flashloan_amount:,.2f} {loan_token_name} (${flashloan_amount*current_price_loan_token:,.2f})", 
        f"{owed_repayment:,.2f} {loan_token_name} (${owed_repayment*current_price_loan_token:,.2f})",
        f"{owed_repayment-flashloan_amount:,.2f} {loan_token_name} (${(owed_repayment-flashloan_amount)*current_price_loan_token:,.2f})",
        f"{sold_on_dex:,.2f} {loan_token_name} (${sold_on_dex*current_price_loan_token:,.2f})",
        f"{received_from_dex:,.2f} {collateral_token_name} (${received_from_dex*current_price_coll_token:,.2f})",
        f"{combined_pledge:,.2f} {collateral_token_name} (${combined_pledge*current_price_coll_token:,.2f})",
        f"{upfront_fee_abs:,.2f} {collateral_token_name} (${upfront_fee_abs*current_price_coll_token:,.2f})",
        f"{myso_fee_abs:,.2f} {collateral_token_name} (${myso_fee_abs*current_price_coll_token:,.2f})",
        f"{final_pledge_and_reclaimable:,.2f} {collateral_token_name} (${final_pledge_and_reclaimable*current_price_coll_token:,.2f})",
        f"{final_pledge_and_reclaimable/user_init_coll_amount:,.2f}x"
    ]
}
st.table(open_position_data)

final_pledge_txt = f"{final_pledge_and_reclaimable:,.2f} {collateral_token_name} (${final_pledge_and_reclaimable*final_price_coll_token:,.2f})" 
final_debt_txt = f"{owed_repayment:,.2f} {loan_token_name} (${owed_repayment*final_price_loan_token:,.2f})"

st.markdown(f"### **Details: Close Looping Position**")
close_position_data = {
    'Description': [
        "Rational to Repay?", 
        "Flashborrow from MYSO Lender", 
        "Sell on DEX", 
        "Receive from DEX",
        "Repayment to MYSO Lender",
        "Gas Cost",
        "Amount Left After Repay and Gas",
        "RoI"
    ],
    'Amount': [
        f"yes, because your reclaimable {final_pledge_txt} collateral is worth more than your {final_debt_txt} debt owed" if rational_to_repay else f"no, because your reclaimable {final_pledge_txt} collateral is worth less than your {final_debt_txt} debt owed",
        f"{flashloan_amount2:,.2f} {collateral_token_name} (${flashloan_amount2*final_price_coll_token:,.2f})", 
        f"{sold_on_dex2:,.2f} {collateral_token_name} (${sold_on_dex2*final_price_coll_token:,.2f})",
        f"{received_from_dex2:,.2f} {loan_token_name} (${received_from_dex2*final_price_loan_token:,.2f})",
        f"{owed_repayment:,.2f} {loan_token_name} (${owed_repayment*final_price_loan_token:,.2f})",
        f"${gas_usd_price}",
        f"{final_amount_after_close2:,.2f} {loan_token_name} (${final_amount_after_close2*final_price_loan_token:,.2f})",
        f"{roi:,.2f}"
    ]
}
st.table(close_position_data)
