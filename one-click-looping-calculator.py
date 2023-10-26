import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
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
    st.title("User Input")
    with st.expander("**Your Collateral Token**", expanded=True):
        collateral_token_name = st.text_input("Name of token you want to lever up", value="WMNT")
        user_init_coll_amount = st.number_input("Amount of **{}** you want to lever up".format(collateral_token_name), min_value=0.1, max_value=100000000000.0, value=380.)
        current_price_coll_token = st.number_input("Current **{}** Price in USD".format(collateral_token_name), value=0.38, format="%.4f")
        st.code(f"Value in USD: ${current_price_coll_token*user_init_coll_amount:,.2f}")

    with st.expander("**Your Loan Token**", expanded=False):
        loan_token_name = st.text_input("Name of token you want to borrow", value="USDT")
        current_price_loan_token = st.number_input("Current **{}** Price in USD".format(loan_token_name), value=1.0, format="%.4f")
        st.code(f"1 {collateral_token_name} = {current_price_coll_token/current_price_loan_token} {loan_token_name}")

    with st.expander("**Your Loan Terms**", expanded=True):
        ltv = st.number_input("LTV", min_value=0.01, max_value=1.0, value=0.8)
        tenor = st.number_input("Tenor* (in days)", min_value=1, max_value=365, value=5)
        apr = st.number_input("APR", min_value=0.0, max_value=1.0, value=0.05)
        upfront_fee = st.number_input("Upfront Fee", min_value=0.0, max_value=1.0, value=0.0, format="%.4f")
        myso_fee = st.number_input("MYSO Protocol Fee", min_value=0.0, value=0.002, max_value=1.0, format="%.4f")

    with st.expander("**Advanced: Input DEX Assumptions**"):
        dex_slippage = st.number_input("DEX Slippage", min_value=0.0, max_value=1.0, value=0.005, format="%.4f")
        dex_swap_fee = st.number_input("DEX Swap Fee", min_value=0.0, max_value=1.0, value=0.0005, format="%.4f")

    with st.expander("**Advanced: Input Gas Price Assumptions**"):
        gas_used = st.number_input("Gas Used (full round trip)", min_value=0, max_value=100000000, value=1200000)
        gas_price = st.number_input("Gas Price (GWei)", min_value=0, max_value=100, value=20)
        eth_price = st.number_input("Gas Token Price (eg MNT price for Mantle)", min_value=0., max_value=10000., value=0.3)
        gas_usd_price = gas_used * gas_price / 10**9 * eth_price
        st.code(f"Gas Cost in USD: ${gas_usd_price:,.2f}")

flashloan_amount, owed_repayment, sold_on_dex, received_from_dex, combined_pledge, upfront_fee_abs, myso_fee_abs, final_pledge_and_reclaimable = calculate_open_position(
    current_price_coll_token, current_price_loan_token, user_init_coll_amount, ltv, apr, upfront_fee, tenor, myso_fee, dex_slippage, dex_swap_fee
)


def roi_function(price_multiplier):
    p1 = current_price_coll_token / current_price_loan_token * price_multiplier
    p2 = current_price_loan_token
    _, _, _, final_amount_after_close2, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_price)
    roi = final_amount_after_close2 * p2 / (current_price_coll_token * user_init_coll_amount) - 1
    return roi

def roi_minus_100_function(price_multiplier):
    p1 = current_price_coll_token / current_price_loan_token * price_multiplier
    p2 = current_price_loan_token
    _, _, _, final_amount_after_close2, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_price)
    roi = final_amount_after_close2 * p2 / (current_price_coll_token * user_init_coll_amount) - 1
    return roi + 1  # Returns the difference between ROI and -100%


st.write(f"""
### What Can I Earn

Define your expected price range for {collateral_token_name}/{loan_token_name} over the upcoming {tenor} days. By doing so, we can explore various market scenarios and determine your potential RoI when looping with MYSO.
""")
# Use a range slider to define the range for hypothetical price changes
price_change_range = st.slider(
    f"**Your expected price range for {collateral_token_name}/{loan_token_name} in {tenor} days:**", 
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
    _, _, _, final_amount_after_close2, _ = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, p1, p2, dex_slippage, dex_swap_fee, gas_usd_price)
    rel_price_changes.append(p1/current_price_coll_token-1)
    RoIs.append(final_amount_after_close2 * p2 / (current_price_coll_token * user_init_coll_amount) - 1)

roi_unchanged = roi_function(1.0) * 100

break_even_multiplier = fsolve(roi_function, 1.0)[0]
break_even_price_change = (break_even_multiplier - 1) * 100

# Using fsolve to find the root of roi_minus_100_function
total_loss_multiplier = fsolve(roi_minus_100_function, 1.0)[0]
total_loss_price_change = (total_loss_multiplier - 1) * 100

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

df = pd.DataFrame(rois_for_changes, columns=["Price Change (%)", "RoI (%)"])
# Expanded DataFrame to include price change bounds, break-even, flat scenario, and full loss
additional_points = [
    {"Price Change (%)": price_change_range[0], "RoI (%)": roi_function(price_change_range[0]/100 + 1) * 100},
    {"Price Change (%)": price_change_range[1], "RoI (%)": roi_function(price_change_range[1]/100 + 1) * 100},
    {"Price Change (%)": break_even_price_change, "RoI (%)": 0},
    {"Price Change (%)": 0, "RoI (%)": roi_unchanged},
    {"Price Change (%)": total_loss_price_change, "RoI (%)": -100},
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
        elif column.name == "RoI (%)":
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
df["Price Change (%)"] = df["Price Change (%)"].apply(lambda x: f"{x:.2f}%")
df["RoI (%)"] = df["RoI (%)"].apply(lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%")


st.write(f"""### Potential Outcomes""")
st.write(f"""Below you can see potential outcomes when looping with MYSO. Your RoI will depend on the realized price change of {collateral_token_name}/{loan_token_name} over the duration of your position.""")
# If you still want to display the full DataFrame below the selected row
styled_df = df.style.apply(highlight_special_points)
st.table(styled_df)
st.write(f"""
    Looping with MYSO effectively sets up a leveraged call option on {collateral_token_name}/{loan_token_name}, where you essentially pay with your initially provided {collateral_token_name} balance. Given a {ltv*100:.1f}% LTV, this results in a {final_pledge_and_reclaimable/user_init_coll_amount:,.2f}x leveraged {collateral_token_name} position. Unlike perpetuals, there's no risk of liquidation, meaning that even if the {collateral_token_name}/{loan_token_name} price drops sharply but later rebounds, you still benefit from the full upside. In a similar situation, a perpetual might be liquidated early, causing a loss. However, there's no guarantee that your leveraged call option will be in-the-money, in particular if the price drops by {total_loss_price_change:.2f}% you will lose all of your {collateral_token_name}.

    A few key points to understand:
    
    - **Break-even**: The price of {collateral_token_name}/{loan_token_name} needs to shift by at least {break_even_price_change:.2f}% for you to break even.

    - **Unwinding Immediately**: If the price of {collateral_token_name}/{loan_token_name} stays constant, or if you decide to unwind your position immediately, your RoI will be {roi_unchanged:.2f}%.

    - **Total Loss**: A drop to {total_loss_price_change:.2f}% in the price of {collateral_token_name}/{loan_token_name} will result in a complete loss.
    """)


   


st.write(f"""### Looping Scenario Deep Dive""")
expected_price_move_coll_token = st.number_input(f"**Input a specific {collateral_token_name}/{loan_token_name} price change you expect during loan tenor for a more in-depth outcome overview.**", min_value=-1.0, max_value=10.0, value=0.05)

final_price_coll_token = current_price_coll_token * (1 + expected_price_move_coll_token)
final_price_loan_token = current_price_loan_token


flashloan_amount2, sold_on_dex2, received_from_dex2, final_amount_after_close2, rational_to_repay = calculate_close_position(final_pledge_and_reclaimable, owed_repayment, final_price_coll_token, final_price_loan_token, dex_slippage, dex_swap_fee, gas_usd_price)

roi = final_amount_after_close2 / (current_price_coll_token * user_init_coll_amount) - 1


st.write(f"""
Based on a {collateral_token_name}/{loan_token_name} price change of {final_price_coll_token/current_price_coll_token/(final_price_loan_token/current_price_loan_token)*100-100:,.2f}%, your resulting RoI would be {100*final_amount_after_close2*final_price_loan_token/(user_init_coll_amount*current_price_coll_token)-100:,.2f}%.

**Detailed Breakdown:**
- **Initial Commitment:** You began your MYSO looping journey with a position of {user_init_coll_amount:,.2f} {collateral_token_name}, equivalent to ${user_init_coll_amount*current_price_coll_token:,.2f}.
  
- **Leverage Effect:** Through leveraging, you magnified this position to {final_pledge_and_reclaimable/user_init_coll_amount:,.2f}x times its initial size.

- **Projected Closing Position:** If the price change materializes as hypothesized, it would be rational for you to {"repay and unwind your looping position" if final_amount_after_close2 > 0 else "default and leave your looping position expire"}, hence your closing position would be {final_amount_after_close2:,.2f} {loan_token_name}, equivalent to ${final_amount_after_close2*final_price_loan_token:,.2f}.
""") 


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
locations = ax.get_xticks()  # Assuming you want to set labels for existing tick locations
ax.xaxis.set_major_locator(plt.FixedLocator(locations))
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
