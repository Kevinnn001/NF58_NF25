import streamlit as st
import os
import datetime
import pytz  # Library for timezone handling
import pandas as pd
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from io import BytesIO
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

# Define the Product model
class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False)

class Cashier:
    def __init__(self):
        # Setup SQLite Database
        self.database_file = 'receipts.db'
        self.setup_database()
        
        # Initialize default products if the products table is empty
        if self.session.query(Product).count() == 0:
            self.initialize_default_products()
    
    def setup_database(self):
        """Initialize the SQLite database and create tables if they don't exist."""
        try:
            self.engine = create_engine(f'sqlite:///{self.database_file}', echo=False, connect_args={'check_same_thread': False})
            Base.metadata.create_all(self.engine)
            Session = sessionmaker(bind=self.engine)
            self.session = Session()
            st.success(f"Database '{self.database_file}' initialized successfully.")
            logger.info(f"Database '{self.database_file}' initialized successfully.")
        except Exception as e:
            st.error(f"Error setting up the database: {e}")
            logger.error(f"Error setting up the database: {e}")
            st.stop()
        
    def initialize_default_products(self):
        """Initialize the database with default products."""
        try:
            default_products = [
                Product(name="布帶", price=30.0, stock=100),
                Product(name="布袋", price=50.0, stock=100),
                Product(name="字母 (大)", price=7.0, stock=200),
                Product(name="字母 (小)", price=5.0, stock=200),
                Product(name="圖案 (大)", price=15.0, stock=150),
                Product(name="圖案 (中)", price=10.0, stock=150),
                Product(name="圖案 (小)", price=5.0, stock=150),
                Product(name="蚯蚓", price=20.0, stock=100),
            ]
            self.session.bulk_save_objects(default_products)
            self.session.commit()
            st.success("Default products initialized.")
            logger.info("Default products initialized in the database.")
        except Exception as e:
            st.error(f"Error initializing default products: {e}")
            logger.error(f"Error initializing default products: {e}")
            self.session.rollback()
            
    def get_all_products(self):
        """Retrieve all products from the database."""
        try:
            products = self.session.query(Product).all()
            return products
        except Exception as e:
            st.error(f"Error retrieving products: {e}")
            logger.error(f"Error retrieving products: {e}")
            return []
    
    def add_product(self, name, price, stock):
        """Add a new product to the database."""
        try:
            new_product = Product(name=name, price=price, stock=stock)
            self.session.add(new_product)
            self.session.commit()
            st.success(f"Product '{name}' added successfully.")
            logger.info(f"Added new product: {name}, Price: {price}, Stock: {stock}.")
        except Exception as e:
            st.error(f"Error adding product: {e}")
            logger.error(f"Error adding product '{name}': {e}")
            self.session.rollback()
    
    def edit_product(self, product_id, name, price, stock):
        """Edit an existing product in the database."""
        try:
            product = self.session.query(Product).filter(Product.id == product_id).first()
            if product:
                product.name = name
                product.price = price
                product.stock = stock
                self.session.commit()
                st.success(f"Product ID {product_id} updated successfully.")
                logger.info(f"Updated product ID {product_id}: {name}, Price: {price}, Stock: {stock}.")
            else:
                st.error(f"No product found with ID {product_id}.")
                logger.warning(f"Attempted to edit non-existent product ID {product_id}.")
        except Exception as e:
            st.error(f"Error editing product: {e}")
            logger.error(f"Error editing product ID {product_id}: {e}")
            self.session.rollback()
    
    def delete_product(self, product_id):
        """Delete a product from the database."""
        try:
            product = self.session.query(Product).filter(Product.id == product_id).first()
            if product:
                self.session.delete(product)
                self.session.commit()
                st.success(f"Product ID {product_id} deleted successfully.")
                logger.info(f"Deleted product ID {product_id}: {product.name}.")
            else:
                st.error(f"No product found with ID {product_id}.")
                logger.warning(f"Attempted to delete non-existent product ID {product_id}.")
        except Exception as e:
            self.session.rollback()
            st.error(f"Error deleting product: {e}")
            logger.error(f"Error deleting product ID {product_id}: {e}")
    
    def add_to_cart(self, cart, product_id, quantity):
        """Add a product to the cart."""
        try:
            product = self.session.query(Product).filter(Product.id == product_id).first()
            if product:
                available_stock = product.stock
                if quantity > available_stock:
                    return f"Cannot add {quantity} x '{product.name}'. Only {available_stock} in stock."
                if product_id in cart:
                    if cart[product_id]["quantity"] + quantity > available_stock:
                        return f"Cannot add {quantity} more x '{product.name}'. Only {available_stock - cart[product_id]['quantity']} more can be added."
                    cart[product_id]["quantity"] += quantity
                else:
                    cart[product_id] = {
                        "name": product.name,
                        "price": product.price,
                        "quantity": quantity,
                    }
                logger.info(f"Added {quantity} x '{product.name}' to the cart.")
                return f"Added {quantity} x '{product.name}' to the cart."
            else:
                return "Invalid Product ID."
        except Exception as e:
            st.error(f"Error adding to cart: {e}")
            logger.error(f"Error adding to cart: {e}")
            return "An error occurred while adding to the cart."
    
    def view_cart(self, cart):
        """Generate a summary of the cart."""
        try:
            if not cart:
                return None, 0  # No items in the cart
            total = 0
            cart_items = []
            for pid, details in cart.items():
                subtotal = details["price"] * details["quantity"]
                total += subtotal
                cart_items.append(
                    {
                        "Product Name": details["name"],
                        "Quantity": details["quantity"],
                        "Price ($)": details["price"],
                        "Subtotal ($)": subtotal,
                    }
                )
            logger.info(f"Viewed cart with total: ${total:.2f}")
            return cart_items, total
        except Exception as e:
            st.error(f"Error viewing cart: {e}")
            logger.error(f"Error viewing cart: {e}")
            return None, 0
    
    def apply_package_discounts(self, cart):
        """Apply package discounts to the cart."""
        try:
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
    
            logger.info(f"Package discounts applied: {details}")
            return savings, details
        except Exception as e:
            st.error(f"Error applying package discounts: {e}")
            logger.error(f"Error applying package discounts: {e}")
            return 0, []
    
    def apply_fixed_discount(self, total):
        """Apply fixed amount discounts based on the total."""
        try:
            applicable_discounts = [d for d in self.fixed_discounts if total >= d["threshold"]]
            if not applicable_discounts:
                return 0, "No Fixed Discounts Applied."
            best_discount = max(applicable_discounts, key=lambda x: x["threshold"])
            logger.info(f"Fixed discount applied: -${best_discount['discount']:.2f}")
            return best_discount["discount"], f"Fixed Discount Applied: -${best_discount['discount']:.2f}"
        except Exception as e:
            st.error(f"Error applying fixed discounts: {e}")
            logger.error(f"Error applying fixed discounts: {e}")
            return 0, "No Fixed Discounts Applied."
    
    def checkout(self, cart, apply_coupon=False):
        """Calculate total and apply discounts."""
        try:
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
    
            logger.info(f"Checkout summary: Final total - ${total_after_coupon:.2f}")
            return output, total_after_coupon, discounts_used
        except Exception as e:
            st.error(f"Error during checkout: {e}")
            logger.error(f"Error during checkout: {e}")
            return "An error occurred during checkout.", 0, []
    
    def log_receipt_to_sqlite(self, cart, total, payment_method, payment_amount, change, discounts_used):
        """Log the receipt to the SQLite database."""
        try:
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
            self.session.add(receipt)
            self.session.commit()
            st.success("Receipt logged successfully in the database.")
            logger.info(f"Receipt {receipt_id} logged successfully.")
        except Exception as e:
            self.session.rollback()
            st.error(f"Failed to log receipt to the database: {e}")
            logger.error(f"Failed to log receipt: {e}")
    
    def get_all_receipts(self):
        """Retrieve all receipts from the database."""
        try:
            receipts = self.session.query(Receipt).all()
            return receipts
        except Exception as e:
            st.error(f"Error retrieving receipts: {e}")
            logger.error(f"Error retrieving receipts: {e}")
            return []
    
    def edit_receipt(self, receipt_id, new_payment_method=None, new_payment_amount=None):
        """Edit an existing receipt's payment method and payment amount."""
        try:
            receipt = self.session.query(Receipt).filter(Receipt.receipt_id == receipt_id).first()
            if receipt:
                if new_payment_method:
                    receipt.payment_method = new_payment_method
                if new_payment_amount is not None:
                    receipt.payment_amount = new_payment_amount
                    # Recalculate change
                    receipt.change = receipt.payment_amount - receipt.final_total
                self.session.commit()
                st.success(f"Receipt ID {receipt_id} has been updated successfully.")
                logger.info(f"Receipt ID {receipt_id} updated: Payment Method - {new_payment_method}, Payment Amount - {new_payment_amount}.")
            else:
                st.error(f"No receipt found with ID {receipt_id}.")
                logger.warning(f"Attempted to edit non-existent receipt ID {receipt_id}.")
        except Exception as e:
            self.session.rollback()
            st.error(f"Error editing receipt: {e}")
            logger.error(f"Error editing receipt ID {receipt_id}: {e}")
    
    def delete_receipt(self, receipt_id):
        """Delete a receipt from the database."""
        try:
            receipt = self.session.query(Receipt).filter(Receipt.receipt_id == receipt_id).first()
            if receipt:
                self.session.delete(receipt)
                self.session.commit()
                st.success(f"Receipt ID {receipt_id} deleted successfully.")
                logger.info(f"Deleted receipt ID {receipt_id}.")
            else:
                st.error(f"No receipt found with ID {receipt_id}.")
                logger.warning(f"Attempted to delete non-existent receipt ID {receipt_id}.")
        except Exception as e:
            self.session.rollback()
            st.error(f"Error deleting receipt: {e}")
            logger.error(f"Error deleting receipt ID {receipt_id}: {e}")
    
    def log_receipt(self, cart, total, payment_method, payment_amount, change, discounts_used):
        """Log the receipt to SQLite and generate receipt content."""
        try:
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
    
            # Log to Database
            self.log_receipt_to_sqlite(cart, total, payment_method, payment_amount, change, discounts_used)
    
            return receipt_content
        except Exception as e:
            st.error(f"Error logging receipt: {e}")
            logger.error(f"Error logging receipt: {e}")
            return "An error occurred while logging the receipt."
    
    def get_receipts_dataframe(self):
        """Convert session receipts to a pandas DataFrame."""
        # For downloading receipts
        try:
            receipts = self.session.query(Receipt).all()
            if not receipts:
                return None
            data = [{
                "Receipt ID": r.receipt_id,
                "Date": r.date.strftime('%Y-%m-%d %H:%M:%S'),
                "Products": r.products,
                "Total Before Discounts": r.total_before_discounts,
                "Discounts Applied": r.discounts_applied,
                "Final Total": r.final_total,
                "Payment Method": r.payment_method,
                "Payment Amount": r.payment_amount,
                "Change": r.change
            } for r in receipts]
            df = pd.DataFrame(data)
            return df
        except Exception as e:
            st.error(f"Error converting receipts to DataFrame: {e}")
            logger.error(f"Error converting receipts to DataFrame: {e}")
            return None
    
    def view_receipts(self):
        """Display all receipts from the database for debugging."""
        try:
            receipts = self.session.query(Receipt).all()
            if receipts:
                data = [{
                    "Receipt ID": r.receipt_id,
                    "Date": r.date.strftime('%Y-%m-%d %H:%M:%S'),
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
if "receipts" not in st.session_state:
    st.session_state.receipts = []

# Initialize Cashier
cashier = Cashier()

# Sidebar Menu
menu_options = ["View Products", "Add to Cart", "View Cart", "Checkout", "Manage Products", "View Receipts"]
menu = st.sidebar.radio("Menu", menu_options)

if menu == "View Products":
    st.header("Available Products")
    products = cashier.get_all_products()
    if products:
        data = [{
            "ID": p.id,
            "Name": p.name,
            "Price ($)": p.price,
            "Stock": p.stock
        } for p in products]
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.info("No products available.")

elif menu == "Add to Cart":
    st.header("Add to Cart")
    # Map product names to IDs for selection
    product_name_to_id = {p.name: p.id for p in cashier.get_all_products()}
    if product_name_to_id:
        product_name = st.selectbox("Select Product", list(product_name_to_id.keys()))
        product_id = product_name_to_id[product_name]
        quantity = st.number_input("Quantity", min_value=1, step=1, value=1)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Add to Cart"):
                message = cashier.add_to_cart(st.session_state.cart, product_id, quantity)
                st.success(message)
        
        with col2:
            if st.button("Clear Cart"):
                st.session_state.cart = {}
                st.success("Cart has been cleared.")
    else:
        st.warning("No products available to add to cart.")

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
        payment_amount = st.number_input("Enter Payment Amount ($)", min_value=0.0, step=0.01, format="%.2f")
        if st.button("Finalize Payment"):
            if payment_amount >= final_total:
                change = payment_amount - final_total
                receipt_content = cashier.log_receipt(
                    st.session_state.cart, final_total, payment_method, payment_amount, change, discounts_used
                )
                st.success(f"Payment successful! Change: ${change:.2f}")
                st.info("Receipt:")
                st.text(receipt_content)
                st.session_state.cart = {}
                
                # Optional: Download Receipts
                df_receipts = cashier.get_receipts_dataframe()
                if df_receipts is not None:
                    towrite = BytesIO()
                    df_receipts.to_excel(towrite, index=False, engine='openpyxl')
                    towrite.seek(0)  # Reset pointer
                    st.download_button(
                        label="Download All Receipts as Excel",
                        data=towrite,
                        file_name='receipts.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
            else:
                st.error(f"Insufficient payment. You still owe ${final_total - payment_amount:.2f}.")

elif menu == "Manage Products":
    st.header("Manage Products")
    sub_menu = st.radio("Select Action", ["View Products", "Add Product", "Edit Product", "Delete Product"])
    
    if sub_menu == "View Products":
        st.subheader("All Products")
        products = cashier.get_all_products()
        if products:
            data = [{
                "ID": p.id,
                "Name": p.name,
                "Price ($)": p.price,
                "Stock": p.stock
            } for p in products]
            df = pd.DataFrame(data)
            st.dataframe(df)
        else:
            st.info("No products available.")
    
    elif sub_menu == "Add Product":
        st.subheader("Add a New Product")
        with st.form(key="add_product_form"):
            name = st.text_input("Product Name")
            price = st.number_input("Price ($)", min_value=0.0, step=0.1)
            stock = st.number_input("Stock Quantity", min_value=0, step=1)
            submit = st.form_submit_button("Add Product")
        
        if submit:
            if name and price >= 0 and stock >= 0:
                cashier.add_product(name, price, stock)
            else:
                st.error("Please provide valid product details.")
    
    elif sub_menu == "Edit Product":
        st.subheader("Edit an Existing Product")
        products = cashier.get_all_products()
        if products:
            product_options = {f"{p.name} (ID: {p.id})": p.id for p in products}
            selected_product = st.selectbox("Select Product to Edit", list(product_options.keys()))
            selected_product_id = product_options[selected_product]
            product = cashier.session.query(Product).filter(Product.id == selected_product_id).first()
            
            if product:
                with st.form(key="edit_product_form"):
                    new_name = st.text_input("Product Name", value=product.name)
                    new_price = st.number_input("Price ($)", min_value=0.0, step=0.1, value=product.price)
                    new_stock = st.number_input("Stock Quantity", min_value=0, step=1, value=product.stock)
                    submit = st.form_submit_button("Update Product")
                
                if submit:
                    if new_name and new_price >= 0 and new_stock >= 0:
                        cashier.edit_product(selected_product_id, new_name, new_price, new_stock)
                    else:
                        st.error("Please provide valid product details.")
        else:
            st.info("No products available to edit.")
    
    elif sub_menu == "Delete Product":
        st.subheader("Delete a Product")
        products = cashier.get_all_products()
        if products:
            product_options = {f"{p.name} (ID: {p.id})": p.id for p in products}
            selected_product = st.selectbox("Select Product to Delete", list(product_options.keys()))
            selected_product_id = product_options[selected_product]
            confirm_delete = st.checkbox("I confirm that I want to delete this product.")
            if st.button("Delete Product"):
                if confirm_delete:
                    cashier.delete_product(selected_product_id)
                else:
                    st.error("Please confirm deletion by checking the box.")
        else:
            st.info("No products available to delete.")

elif menu == "View Receipts":
    st.header("All Receipts")
    receipts = cashier.get_all_receipts()
    
    if receipts:
        # Display receipts in a table
        data = [{
            "Receipt ID": r.receipt_id,
            "Date": r.date.strftime('%Y-%m-%d %H:%M:%S'),
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
        
        st.markdown("---")
        st.subheader("Edit a Receipt")
        
        # Select Receipt to Edit
        receipt_ids = [receipt.receipt_id for receipt in receipts]
        selected_receipt_id = st.selectbox("Select Receipt ID to Edit", receipt_ids)
        
        # Fetch the selected receipt
        selected_receipt = cashier.session.query(Receipt).filter(Receipt.receipt_id == selected_receipt_id).first()
        
        if selected_receipt:
            with st.form(key="edit_receipt_form"):
                st.write(f"**Editing Receipt ID:** {selected_receipt_id}")
                new_payment_method = st.selectbox(
                    "Payment Method", 
                    ["Cash", "PayMe", "支付寶", "轉數快"], 
                    index=["Cash", "PayMe", "支付寶", "轉數快"].index(selected_receipt.payment_method) if selected_receipt.payment_method in ["Cash", "PayMe", "支付寶", "轉數快"] else 0
                )
                new_payment_amount = st.number_input("Payment Amount ($)", min_value=0.0, step=0.01, value=selected_receipt.payment_amount)
                submit_button = st.form_submit_button("Update Receipt")
            
            if submit_button:
                if new_payment_amount < selected_receipt.final_total:
                    st.error(f"Payment amount cannot be less than the final total (${selected_receipt.final_total:.2f}).")
                else:
                    cashier.edit_receipt(
                        receipt_id=selected_receipt_id, 
                        new_payment_method=new_payment_method, 
                        new_payment_amount=new_payment_amount
                    )
                    
                    # Refresh the receipts list
                    st.experimental_rerun()
        else:
            st.error("Selected receipt not found.")
        
        st.markdown("---")
        st.subheader("Delete a Receipt")
        
        with st.form(key="delete_receipt_form"):
            delete_receipt_id = st.selectbox("Select Receipt ID to Delete", receipt_ids)
            delete_confirm = st.checkbox("I confirm that I want to delete this receipt.")
            delete_submit = st.form_submit_button("Delete Receipt")
        
        if delete_submit:
            if delete_confirm:
                cashier.delete_receipt(receipt_id=delete_receipt_id)
                st.experimental_rerun()
            else:
                st.error("Please confirm the deletion by checking the box.")
    else:
        st.info("No receipts found in the database.")
