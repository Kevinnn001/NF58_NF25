import streamlit as st
import os
import datetime
import pytz  # Library for timezone handling
import pandas as pd
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

# Configure logging
logging.basicConfig(
    filename='app.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger()

# Define the ORM base
Base = declarative_base()

# Define the Receipt model
class Receipt(Base):
    __tablename__ = 'receipts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(String, unique=True, nullable=False)
    date = Column(DateTime, nullable=False)
    products = Column(Text, nullable=False)
    total_before_discounts = Column(Float, nullable=False)
    discounts_applied = Column(Text, nullable=True)
    final_total = Column(Float, nullable=False)
    payment_method = Column(String, nullable=False)
    payment_amount = Column(Float, nullable=False)
    change = Column(Float, nullable=False)

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

        # Setup SQLite Database
        self.database_file = 'receipts.db'
        self.setup_database()

    def setup_database(self):
        """Initialize the SQLite database and create tables if they don't exist."""
        try:
            self.engine = create_engine(f'sqlite:///{self.database_file}', echo=False)
            Base.metadata.create_all(self.engine)
            Session = sessionmaker(bind=self.engine)
            self.session = Session()
            st.success(f"Database '{self.database_file}' initialized successfully.")
            logger.info(f"Database '{self.database_file}' initialized successfully.")
        except Exception as e:
            st.error(f"Error setting up the database: {e}")
            logger.error(f"Error setting up the database: {e}")

        # Display absolute path for confirmation
        abs_path = os.path.abspath(self.database_file)
        st.write(f"Database absolute path: {abs_path}")
        logger.info(f"Database absolute path: {abs_path}")

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

    def log_receipt_to_sqlite(self, cart, total, payment_method, payment_amount, change, discounts_used):
        """Log the receipt to the SQLite database."""
        receipt_id = datetime.datetime.now().strftime('%Y%m%d%H%M%S')  # Unique ID based on timestamp
        utc_now = datetime.datetime.now(pytz.utc).astimezone(pytz.timezone("Asia/Hong_Kong"))
        date_obj = utc_now.replace(tzinfo=None)  # Remove timezone info for storage

        # Create a summary of the products
        products_summary = "; ".join([f"{details['name']} x {details['quantity']}" for details in cart.values()])

        # Create a summary of discounts
        discounts_summary = "; ".join(discounts_used) if discounts_used else "None"

        # Calculate total before discounts
        total_before_discounts = sum(details['price'] * details['quantity'] for details in cart.values())

        # Create a Receipt instance
        receipt = Receipt(
            receipt_id=receipt_id,
            date=date_obj,
            products=products_summary,
            total_before_discounts=total_before_discounts,
            discounts_applied=discounts_summary,
            final_total=total,
            payment_method=payment_method,
            payment_amount=payment_amount,
            change=change
        )

        # Add to session and commit
        try:
            self.session.add(receipt)
            self.session.commit()
            st.success("Receipt logged successfully in the database.")
            logger.info(f"Receipt {receipt_id} logged successfully.")
        except Exception as e:
            self.session.rollback()
            st.error(f"Failed to log receipt to the database: {e}")
            logger.error(f"Failed to log receipt {receipt_id}: {e}")

    def log_receipt(self, cart, total, payment_method, payment_amount, change, discounts_used):
        """Log the receipt to SQLite and generate receipt content."""
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

        # Log to SQLite
        self.log_receipt_to_sqlite(cart, total, payment_method, payment_amount, change, discounts_used)

        return receipt_content

    def view_receipts(self):
        """Display all receipts from the database for debugging."""
        try:
            receipts = self.session.query(Receipt).all()
            if receipts:
                data = [{
                    "Receipt ID": r.receipt_id,
                    "Date": r.date,
                    "Products": r.products,
                    "Total Before Discounts": r.total_before_discounts,
                    "Discounts Applied": r.discounts_applied,
                    "Final Total": r.final_total,
                    "Payment Method": r.payment_method,
                    "Payment Amount": r.payment_amount,
                    "Change": r.change
                } for r in receipts]
                df = pd.DataFrame(data)
                st.dataframe(df)
                logger.info("Displayed all receipts.")
            else:
                st.info("No receipts found in the database.")
                logger.info("No receipts found in the database to display.")
        except Exception as e:
            st.error(f"Failed to retrieve receipts: {e}")
            logger.error(f"Failed to retrieve receipts: {e}")

# Initialize the Streamlit App
st.title("印蛇出動 NF25 & NF58")

# Initialize session state
if "cart" not in st.session_state:
    st.session_state.cart = {}

# Initialize Cashier
cashier = Cashier()

# List directory contents for debugging
st.write("#### Current Directory Contents:")
dir_contents = os.listdir('.')
st.write(dir_contents)
logger.info(f"Current directory contents: {dir_contents}")

# Sidebar Menu
menu = st.sidebar.radio("Menu", ["View Products", "Add to Cart", "View Cart", "Checkout", "View Receipts"])

if menu == "View Products":
    st.header("Available Products")
    for pid, details in cashier.products.items():
        st.write(f"{pid}: {details['name']} - ${details['price']} (Stock: {details['stock']})")

elif menu == "Add to Cart":
    st.header("Add to Cart")

    # Map product names to IDs for selection
    product_name_to_id = {details["name"]: pid for pid, details in cashier.products.items()}
    product_name = st.selectbox("Select Product", list(product_name_to_id.keys()))
    product_id = product_name_to_id[product_name]

    quantity = st.number_input("Quantity", min_value=1, step=1, value=1)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Add to Cart"):
            message = cashier.add_to_cart(st.session_state.cart, product_id, quantity)
            st.success(message)
            logger.info(f"Added {quantity} x '{cashier.products[product_id]['name']}' to the cart.")

    with col2:
        if st.button("Clear Cart"):
            st.session_state.cart = {}
            st.success("Cart has been cleared.")
            logger.info("Cleared the cart.")

elif menu == "View Cart":
    st.header("Your Cart")
    cart_items, total = cashier.view_cart(st.session_state.cart)
    if cart_items is None:
        st.warning("Your cart is empty.")
    else:
        st.table(cart_items)
        st.write(f"Total: ${total:.2f}")
        logger.info(f"Viewed cart with total: ${total:.2f}")

elif menu == "Checkout":
    st.header("Checkout")
    apply_coupon = st.checkbox("Apply Coupon ($5 off)")
    checkout_summary, final_total, discounts_used = cashier.checkout(st.session_state.cart, apply_coupon=apply_coupon)
    st.text(checkout_summary)
    logger.info(f"Checkout summary generated with final total: ${final_total:.2f}")

    if final_total > 0:
        payment_method = st.selectbox("Select Payment Method", ["Cash", "PayMe", "支付寶", "轉數快"])
        payment_amount = st.number_input("Enter Payment Amount", min_value=0.0, step=0.01, format="%.2f")
        if st.button("Finalize Payment"):
            if payment_amount >= final_total:
                change = payment_amount - final_total
                receipt_content = cashier.log_receipt(
                    st.session_state.cart, final_total, payment_method, payment_amount, change, discounts_used
                )
                st.success(f"Payment successful! Change: ${change:.2f}")
                st.info("Receipt:")
                st.text(receipt_content)
                logger.info(f"Payment finalized. Change given: ${change:.2f}")
                st.session_state.cart = {}
                logger.info("Cart cleared after payment.")
            else:
                st.error(f"Insufficient payment. You still owe ${final_total - payment_amount:.2f}.")
                logger.warning(f"Insufficient payment: Paid ${payment_amount:.2f}, owed ${final_total - payment_amount:.2f}.")

elif menu == "View Receipts":
    st.header("All Receipts")
    cashier.view_receipts()
