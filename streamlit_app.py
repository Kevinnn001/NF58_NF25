pip install openpyxl

import streamlit as st
import os
import datetime
import pytz  # Library for timezone handling
import pandas as pd

# Define the Cashier class
class Cashier:
    def __init__(self):
        # Define products with initial stock
        self.products = {
            1: {"name": "布帶", "price": 30, "stock": 100},
            2: {"name": "布袋", "price": 50, "stock": 100},
            3: {"name": "字母 (大)", "price": 7, "stock": 200},
            4: {"name": "字母 (小)", "price": 5, "stock": 200},
            5: {"name": "圖案 (大)", "price": 15, "stock": 150},
            6: {"name": "圖案 (中)", "price": 10, "stock": 150},
            7: {"name": "圖案 (小)", "price": 5, "stock": 150},
            8: {"name": "蚯蚓", "price": 20, "stock": 100},
        }

        # Define package discounts
        self.packages = [
            {"name": "一袋一布帶", "required_products": {1: 1, 2: 1}, "discount": 10},
            {"name": "兩布帶", "required_products": {1: 2}, "discount": 5},
            {"name": "兩袋", "required_products": {2: 2}, "discount": 10},
        ]

        # Define fixed amount discounts
        self.fixed_discounts = [
            {"threshold": 220, "discount": 20},
            {"threshold": 350, "discount": 40},
        ]

        # Define the receipt log Excel file
        self.excel_file = "receipts.xlsx"
        self.excel_sheet = "Receipts"

        # Initialize the Excel file with headers if it doesn't exist
        if not os.path.exists(self.excel_file):
            df = pd.DataFrame(columns=[
                "Receipt ID",
                "Date",
                "Products",
                "Total Before Discounts",
                "Discounts Applied",
                "Final Total",
                "Payment Method",
                "Payment Amount",
                "Change"
            ])
            df.to_excel(self.excel_file, index=False, sheet_name=self.excel_sheet)

    def add_to_cart(self, cart, product_id, quantity):
        """Add a product to the cart."""
        if product_id in self.products:
            available_stock = self.products[product_id]["stock"]
            if quantity > available_stock:
                return f"Cannot add {quantity} x '{self.products[product_id]['name']}'. Only {available_stock} in stock."
            if product_id in cart:
                if cart[product_id]["quantity"] + quantity > available_stock:
                    return f"Cannot add {quantity} more x '{self.products[product_id]['name']}'. Only {available_stock - cart[product_id]['quantity']} more can be added."
                cart[product_id]["quantity"] += quantity
            else:
                cart[product_id] = {
                    "name": self.products[product_id]["name"],
                    "price": self.products[product_id]["price"],
                    "quantity": quantity,
                }
            return f"Added {quantity} x '{self.products[product_id]['name']}' to the cart."
        else:
            return "Invalid Product ID."

    def view_cart(self, cart):
        """Generate a summary of the cart."""
        if not cart:
            return None, 0  # No items in the cart
        total = 0
        cart_items = []
        for pid, details in cart.items():
            subtotal = details["price"] * details["quantity"]
            total += subtotal
            cart_items.append(
                {
                    "Product Name": details["name"],  # Use product name instead of ID
                    "Quantity": details["quantity"],
                    "Price ($)": details["price"],
                    "Subtotal ($)": subtotal,
                }
            )
        return cart_items, total

    def apply_package_discounts(self, cart):
        """Apply package discounts to the cart."""
        savings = 0
        details = []
        available_quantities = {pid: details["quantity"] for pid, details in cart.items()}

        for package in self.packages:
            required_products = package["required_products"]
            discount_amount = package["discount"]
            package_name = package["name"]
            times_applicable = float("inf")

            for pid, qty_required in required_products.items():
                if pid not in available_quantities or available_quantities[pid] < qty_required:
                    times_applicable = 0
                    break
                times_applicable = min(times_applicable, available_quantities[pid] // qty_required)

            if times_applicable > 0:
                savings += discount_amount * times_applicable
                details.append(
                    f"Applied package '{package_name}' {times_applicable} time(s): -${discount_amount * times_applicable:.2f}"
                )
                for pid, qty_required in required_products.items():
                    available_quantities[pid] -= qty_required * times_applicable

        return savings, details

    def apply_fixed_discount(self, total):
        """Apply fixed amount discounts based on the total."""
        applicable_discounts = [d for d in self.fixed_discounts if total >= d["threshold"]]
        if not applicable_discounts:
            return 0, "No Fixed Discounts Applied."
        best_discount = max(applicable_discounts, key=lambda x: x["threshold"])
        return best_discount["discount"], f"Fixed Discount Applied: -${best_discount['discount']:.2f}"

    def checkout(self, cart, apply_coupon=False):
        """Calculate total and apply discounts."""
        if not cart:
            return "Your cart is empty.", 0, []

        total_before_discounts = sum(
            details["price"] * details["quantity"] for details in cart.values()
        )
        output = f"Total before discounts: ${total_before_discounts:.2f}\n"

        package_savings, package_details = self.apply_package_discounts(cart)
        total_after_packages = total_before_discounts - package_savings
        output += f"Package Discounts Savings: -${package_savings:.2f}\n"
        for detail in package_details:
            output += detail + "\n"

        fixed_discount, fixed_discount_msg = self.apply_fixed_discount(total_after_packages)
        total_after_fixed = total_after_packages - fixed_discount
        output += fixed_discount_msg + "\n"

        coupon_savings = 0
        if apply_coupon:
            coupon_savings = 5
            output += f"Coupon Savings: -$5.00\n"

        total_after_coupon = total_after_fixed - coupon_savings
        output += f"Final Total: ${total_after_coupon:.2f}\n"

        # Collect all discounts for the receipt
        discounts_used = package_details
        if fixed_discount > 0:
            discounts_used.append(f"Fixed Discount: -${fixed_discount:.2f}")
        if apply_coupon:
            discounts_used.append("Coupon Discount: -$5.00")

        return output, total_after_coupon, discounts_used

    def log_receipt_to_excel(self, cart, total, payment_method, payment_amount, change, discounts_used):
        """Log the receipt to an Excel file."""
        receipt_id = datetime.datetime.now().strftime('%Y%m%d%H%M%S')  # Unique ID based on timestamp
        utc_now = datetime.datetime.now(pytz.utc).astimezone(pytz.timezone("Asia/Hong_Kong"))
        date_str = utc_now.strftime('%Y-%m-%d %H:%M:%S')

        # Create a summary of the products
        products_summary = "; ".join([f"{details['name']} x {details['quantity']}" for details in cart.values()])

        # Create a summary of discounts
        discounts_summary = "; ".join(discounts_used) if discounts_used else "None"

        # Prepare the data row
        receipt_data = {
            "Receipt ID": receipt_id,
            "Date": date_str,
            "Products": products_summary,
            "Total Before Discounts": sum(details['price'] * details['quantity'] for details in cart.values()),
            "Discounts Applied": discounts_summary,
            "Final Total": total,
            "Payment Method": payment_method,
            "Payment Amount": payment_amount,
            "Change": change
        }

        # Convert to DataFrame
        df = pd.DataFrame([receipt_data])

        # Check if file exists to determine header
        file_exists = os.path.isfile(self.excel_file)

        # Append to the Excel file
        with pd.ExcelWriter(self.excel_file, engine='openpyxl', mode='a' if file_exists else 'w', if_sheet_exists='overlay') as writer:
            # Write the DataFrame to the sheet
            df.to_excel(writer, index=False, header=not file_exists, sheet_name=self.excel_sheet, startrow=writer.sheets[self.excel_sheet].max_row if file_exists else 0)

        return receipt_data  # Optional: Return the data if needed elsewhere

    def log_receipt(self, cart, total, payment_method, payment_amount, change, discounts_used):
        """Log the receipt to an Excel file."""
        # Generate receipt content for display (optional)
        utc_now = datetime.datetime.now(pytz.utc).astimezone(pytz.timezone("Asia/Hong_Kong"))
        receipt_content = f"--- Receipt ---\n"
        receipt_content += f"Date: {utc_now.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)\n\n"

        receipt_content += "{:<20} {:<10} {:<10} {:<10}\n".format(
            "Product Name", "Quantity", "Price ($)", "Subtotal ($)"
        )
        receipt_content += "-" * 60 + "\n"

        for pid, details in cart.items():
            subtotal = details["price"] * details["quantity"]
            receipt_content += "{:<20} {:<10} {:<10} {:<10}\n".format(
                details["name"], details["quantity"], details["price"], subtotal
            )

        receipt_content += "-" * 60 + "\n"
        receipt_content += f"Total Before Discounts: ${sum(details['price'] * details['quantity'] for details in cart.values()):.2f}\n"

        # Include the discounts applied
        receipt_content += "\n--- Discounts Applied ---\n"
        for discount in discounts_used:
            receipt_content += discount + "\n"

        receipt_content += f"\nFinal Total: ${total:.2f}\n"
        receipt_content += f"Payment Method: {payment_method}\n"
        receipt_content += f"Payment Amount: ${payment_amount:.2f}\n"
        receipt_content += f"Change: ${change:.2f}\n"
        receipt_content += "--- Thank You! ---\n\n"

        # Log to Excel
        self.log_receipt_to_excel(cart, total, payment_method, payment_amount, change, discounts_used)

        return receipt_content

# Streamlit App
st.title("印蛇出動 NF25 & NF58")

# Initialize session state
if "cart" not in st.session_state:
    st.session_state.cart = {}

cashier = Cashier()

menu = st.sidebar.radio("Menu", ["View Products", "Add to Cart", "View Cart", "Checkout"])

if menu == "View Products":
    st.header("Available Products")
    for pid, details in cashier.products.items():
        st.write(f"{pid}: {details['name']} - ${details['price']} (Stock: {details['stock']})")

elif menu == "Add to Cart":
    st.header("Add to Cart")
    
    product_name_to_id = {details["name"]: pid for pid, details in cashier.products.items()}
    product_name = st.selectbox("Select Product", list(product_name_to_id.keys()))
    product_id = product_name_to_id[product_name]
    
    quantity = st.number_input("Quantity", min_value=1, step=1)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Add to Cart"):
            message = cashier.add_to_cart(st.session_state.cart, product_id, quantity)
            st.success(message)
    
    with col2:
        if st.button("Clear Cart"):
            st.session_state.cart = {}
            st.success("Cart has been cleared.")

elif menu == "View Cart":
    st.header("Your Cart")
    cart_items, total = cashier.view_cart(st.session_state.cart)
    if cart_items is None:
        st.warning("Your cart is empty.")
    else:
        st.table(cart_items)
        st.write(f"Total: ${total:.2f}")

elif menu == "Checkout":
    st.header("Checkout")
    apply_coupon = st.checkbox("Apply Coupon ($5 off)")
    checkout_summary, final_total, discounts_used = cashier.checkout(st.session_state.cart, apply_coupon=apply_coupon)
    st.text(checkout_summary)

    if final_total > 0:
        payment_method = st.selectbox("Select Payment Method", ["Cash", "PayMe", "支付寶", "轉數快"])
        payment_amount = st.number_input("Enter Payment Amount", min_value=0.0, step=0.01)
        if st.button("Finalize Payment"):
            if payment_amount >= final_total:
                change = payment_amount - final_total
                receipt_content = cashier.log_receipt(
                    st.session_state.cart, final_total, payment_method, payment_amount, change, discounts_used
                )
                st.success(f"Payment successful! Change: ${change:.2f}")
                st.info("Receipt logged successfully in Excel.")
                st.text(receipt_content)
                st.session_state.cart = {}
            else:
                st.error(f"Insufficient payment. You still owe ${final_total - payment_amount:.2f}.")
