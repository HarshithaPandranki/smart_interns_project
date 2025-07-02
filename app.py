from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_cors import CORS
import boto3
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key'
CORS(app)

# AWS DynamoDB and SNS setup
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')

user_table = dynamodb.Table('Users')
review_table = dynamodb.Table('Reviews')
cart_table = dynamodb.Table('Cart')

# Replace with your SNS Topic ARN
order_topic_arn = 'arn:aws:sns:us-east-1:xxxxxxxxxxxx:OrderNotifications'

def is_logged_in():
    return 'user' in session

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            response = user_table.get_item(Key={'email': email})
            user = response.get('Item')
            if user and user['password'] == password:
                session['user'] = user['name']
                session['email'] = user['email']
                return redirect(url_for('home'))
            else:
                flash("Invalid credentials")
        except Exception as e:
            flash("Login error: " + str(e))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        try:
            if 'Item' in user_table.get_item(Key={'email': email}):
                flash("Email already registered.")
                return redirect(url_for('register'))
            user_table.put_item(Item={
                'email': email,
                'name': name,
                'phone': phone,
                'password': password
            })
            session['user'] = name
            session['email'] = email
            return redirect(url_for('home'))
        except Exception as e:
            flash("Registration error: " + str(e))
    return render_template('register.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    return render_template('home.html', user=session.get('user'))

@app.route('/cart', methods=['GET', 'POST'])
def cart():
    email = session.get('email')
    if not email:
        return redirect(url_for('login'))
    if request.method == 'POST':
        item = request.form['item']
        weight = request.form['weight']
        quantity = int(request.form['quantity'])
        cart_table.put_item(Item={
            'id': str(uuid.uuid4()),
            'email': email,
            'item': item,
            'weight': weight,
            'quantity': quantity,
            'timestamp': str(datetime.now())
        })
        flash("Item added to cart.")
    response = cart_table.scan()
    items = [i for i in response['Items'] if i['email'] == email]
    return render_template('viewcart.html', items=items)

@app.route('/order', methods=['GET', 'POST'])
def order():
    email = session.get('email')
    name = session.get('user')
    if not email:
        return redirect(url_for('login'))

    response = cart_table.scan()
    items = [i for i in response['Items'] if i['email'] == email]

    if request.method == 'POST':
        address = request.form['address']
        message = f"Order by {name} ({email})\nAddress: {address}\n\nItems:\n"
        for item in items:
            message += f"{item['quantity']} x {item['item']} ({item['weight']}g)\n"

        try:
            sns.publish(
                TopicArn=order_topic_arn,
                Message=message,
                Subject='New Order from MOMade Pickles'
            )
        except Exception as e:
            flash("SNS Error: " + str(e))

        flash("Order placed successfully!")
        return redirect(url_for('home'))

    return render_template('order.html', items=items)

@app.route('/reviews', methods=['GET', 'POST'])
def reviews():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        review_table.put_item(Item={
            'id': str(uuid.uuid4()),
            'name': name,
            'email': email,
            'message': message
        })
        flash("Review submitted!")
    reviews = review_table.scan().get('Items', [])
    return render_template('reviews.html', reviews=reviews)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for('welcome'))

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', is_logged_in=is_logged_in()), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html', is_logged_in=is_logged_in()), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
