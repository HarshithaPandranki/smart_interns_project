from flask import Flask, render_template, request, redirect, url_for, session, flash
import boto3
import uuid
from datetime import datetime
from dotenv import load_dotenv
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Initialize DynamoDB
region_name = 'ap-south-1'
dynamodb = boto3.resource('dynamodb', region_name=region_name)
cart_table = dynamodb.Table('Cart')
reviews_table = dynamodb.Table('Reviews')
users_table = dynamodb.Table('Users')

# Function to send order confirmation email
def send_confirmation_email(to_email, address):
    from_email = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_APP_PASSWORD")

    subject = "MOMade Pickles - Order Confirmation"
    body = f"""
    Hello,

    Thank you for your order from MOMade Pickles!

    Your items will be delivered to the following address:
    {address}

    Payment Mode: Cash on Delivery (COD)

    We appreciate your support!

    Regards,
    MOMade Pickles Team
    """

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(from_email, password)
            server.send_message(msg)
    except Exception as e:
        print(f"Error sending email: {e}")

# ------------------------ Add to Cart Route ------------------------
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'email' not in session:
        flash("Please login first.")
        return redirect(url_for('login'))

    email = session['email']
    item_name = request.form.get('name')
    weight = int(request.form.get('weight'))
    quantity = int(request.form.get('quantity'))

    price_per_unit = {
        250: 100,
        500: 180,
        1000: 340
    }

    price = price_per_unit.get(weight, 0)
    total = price * quantity

    item_id = str(uuid.uuid4())

    cart_table.put_item(
        Item={
            'email': email,
            'item_id': item_id,
            'item_name': item_name,
            'weight': weight,
            'quantity': quantity,
            'price': price,
            'total': total,
            'timestamp': datetime.now().isoformat()
        }
    )

    flash("Item added to cart!")
    return redirect(url_for('home'))

# ------------------------ View Cart Route ------------------------
@app.route('/viewcart')
def view_cart():
    if 'email' not in session:
        flash("Please login to view your cart.")
        return redirect(url_for('login'))

    email = session['email']
    response = cart_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('email').eq(email)
    )
    cart_items = response.get('Items', [])

    return render_template('viewcart.html', cart=cart_items)

# ------------------------ Order Route ------------------------
@app.route('/order', methods=['GET', 'POST'])
def order():
    if 'email' not in session:
        flash("Please login to place an order.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        email = session['email']
        address = request.form.get('address')

        response = cart_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('email').eq(email)
        )
        items = response.get('Items', [])

        for item in items:
            cart_table.delete_item(
                Key={
                    'email': email,
                    'item_id': item['item_id']
                }
            )

        send_confirmation_email(email, address)

        flash("Order placed successfully! (COD)")
        return redirect(url_for('home'))

    return render_template('order.html')

# ------------------------ Review Route ------------------------
@app.route('/reviews', methods=['GET', 'POST'])
def reviews():
    if request.method == 'POST':
        if 'email' not in session:
            flash("Please login to write a review.")
            return redirect(url_for('login'))

        name = request.form.get('name')
        message = request.form.get('message')
        email = session['email']

        reviews_table.put_item(
            Item={
                'email': email,
                'timestamp': datetime.now().isoformat(),
                'name': name,
                'message': message
            }
        )
        flash("Thank you for your feedback!")
        return redirect(url_for('reviews'))

    dummy_reviews = [
        {'name': 'Akhila', 'message': 'Loved the mango pickle! Tastes just like homemade.'},
        {'name': 'Sai', 'message': 'Snacks are super fresh and crunchy. Must try!'},
        {'name': 'Pooja', 'message': 'Excellent quality and packaging. Will order again.'}
    ]

    return render_template('reviews.html', reviews=dummy_reviews)

# ------------------------ Register Route ------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')

        users_table.put_item(
            Item={
                'email': email,
                'name': name,
                'phone': phone,
                'password': password
            }
        )
        flash("Registration successful! Please login.")
        return redirect(url_for('login'))

    return render_template('register.html')

# ------------------------ Login Route ------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        response = users_table.get_item(Key={'email': email})
        user = response.get('Item')

        if user and user['password'] == password:
            session['email'] = email
            flash("Login successful!")
            return redirect(url_for('home'))
        else:
            flash("Invalid credentials. Please try again.")

    return render_template('login.html')

# ------------------------ Dummy Routes ------------------------
@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
