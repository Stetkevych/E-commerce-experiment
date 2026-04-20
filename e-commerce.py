"""
E-Commerce API using Flask, Flask-SQLAlchemy, Flask-Marshmallow, and MySQL
Manages Users, Orders, and Products with One-to-Many and Many-to-Many relationships
"""

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from marshmallow import fields, ValidationError
from datetime import datetime
import os

# Initialize Flask App
app = Flask(__name__)

# MySQL Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:root@localhost/ecommerce_api'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Extensions
db = SQLAlchemy(app)
ma = Marshmallow(app)

# ============================================================================
# DATABASE MODELS
# ============================================================================

class User(db.Model):
    """User model for storing customer information"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    
    # Relationship: One User -> Many Orders
    orders = db.relationship('Order', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.name}>'


class Product(db.Model):
    """Product model for storing product information"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    
    # Many-to-Many relationship with Order through association table
    orders = db.relationship('Order', secondary='order_product', backref='products')
    
    def __repr__(self):
        return f'<Product {self.product_name}>'


class Order(db.Model):
    """Order model for storing order information"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.DateTime, default=datetime.now, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    def __repr__(self):
        return f'<Order {self.id} - User {self.user_id}>'


class OrderProduct(db.Model):
    """Association table for Many-to-Many relationship between Order and Product"""
    __tablename__ = 'order_product'
    
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), primary_key=True)
    
    def __repr__(self):
        return f'<OrderProduct Order:{self.order_id} Product:{self.product_id}>'


# ============================================================================
# MARSHMALLOW SCHEMAS
# ============================================================================

class UserSchema(ma.SQLAlchemyAutoSchema):
    """Schema for User model - serialization and validation"""
    
    class Meta:
        model = User
        load_instance = True
        include_fk = True
    
    # Validate email format
    email = fields.Email(required=True, validate=lambda x: '@' in x)
    name = fields.String(required=True, validate=lambda x: len(x) > 0)
    address = fields.String(required=True)
    
    # Nested relationship for orders
    orders = fields.Nested('OrderSchema', many=True, dump_only=True)


class ProductSchema(ma.SQLAlchemyAutoSchema):
    """Schema for Product model - serialization and validation"""
    
    class Meta:
        model = Product
        load_instance = True
    
    product_name = fields.String(required=True, validate=lambda x: len(x) > 0)
    price = fields.Float(required=True, validate=lambda x: x > 0)


class OrderSchema(ma.SQLAlchemyAutoSchema):
    """Schema for Order model - serialization and validation"""
    
    class Meta:
        model = Order
        load_instance = True
        include_fk = True  # Include foreign keys
    
    user_id = fields.Integer(required=True)
    order_date = fields.DateTime()
    
    # Nested relationships
    user = fields.Nested(UserSchema, dump_only=True)
    products = fields.Nested(ProductSchema, many=True, dump_only=True)


# ============================================================================
# INITIALIZATION
# ============================================================================

@app.before_first_request
def create_tables():
    """Create all database tables"""
    db.create_all()
    print("Database tables created successfully!")


# ============================================================================
# USER ENDPOINTS
# ============================================================================

@app.route('/users', methods=['GET'])
def get_users():
    """Retrieve all users"""
    try:
        users = User.query.all()
        schema = UserSchema(many=True)
        return jsonify(schema.dump(users)), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Retrieve a user by ID"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        schema = UserSchema()
        return jsonify(schema.dump(user)), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/users', methods=['POST'])
def create_user():
    """Create a new user"""
    try:
        schema = UserSchema()
        data = request.get_json()
        
        # Validate data
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Check if email already exists
        if User.query.filter_by(email=data.get('email')).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        # Create new user
        user = User(
            name=data.get('name'),
            address=data.get('address'),
            email=data.get('email')
        )
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify(schema.dump(user)), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update a user by ID"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
        if 'name' in data:
            user.name = data['name']
        if 'address' in data:
            user.address = data['address']
        if 'email' in data:
            # Check if new email is unique
            existing_user = User.query.filter_by(email=data['email']).first()
            if existing_user and existing_user.id != user_id:
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data['email']
        
        db.session.commit()
        schema = UserSchema()
        return jsonify(schema.dump(user)), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete a user by ID"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'message': f'User {user_id} deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# PRODUCT ENDPOINTS
# ============================================================================

@app.route('/products', methods=['GET'])
def get_products():
    """Retrieve all products"""
    try:
        products = Product.query.all()
        schema = ProductSchema(many=True)
        return jsonify(schema.dump(products)), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Retrieve a product by ID"""
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        schema = ProductSchema()
        return jsonify(schema.dump(product)), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/products', methods=['POST'])
def create_product():
    """Create a new product"""
    try:
        schema = ProductSchema()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Create new product
        product = Product(
            product_name=data.get('product_name'),
            price=data.get('price')
        )
        
        db.session.add(product)
        db.session.commit()
        
        return jsonify(schema.dump(product)), 201
    except ValidationError as err:
        return jsonify({'error': err.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Update a product by ID"""
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        data = request.get_json()
        
        if 'product_name' in data:
            product.product_name = data['product_name']
        if 'price' in data:
            if data['price'] <= 0:
                return jsonify({'error': 'Price must be greater than 0'}), 400
            product.price = data['price']
        
        db.session.commit()
        schema = ProductSchema()
        return jsonify(schema.dump(product)), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Delete a product by ID"""
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({'message': f'Product {product_id} deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ORDER ENDPOINTS
# ============================================================================

@app.route('/orders', methods=['POST'])
def create_order():
    """Create a new order"""
    try:
        schema = OrderSchema()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Verify user exists
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Create new order
        order = Order(
            user_id=user_id,
            order_date=datetime.utcnow()
        )
        
        db.session.add(order)
        db.session.commit()
        
        return jsonify(schema.dump(order)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/orders/<int:order_id>/add_product/<int:product_id>', methods=['PUT'])
def add_product_to_order(order_id, product_id):
    """Add a product to an order (prevent duplicates)"""
    try:
        # Verify order exists
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Verify product exists
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Check if product already in order
        existing = OrderProduct.query.filter_by(
            order_id=order_id,
            product_id=product_id
        ).first()
        
        if existing:
            return jsonify({'error': 'Product already in this order'}), 400
        
        # Add product to order
        order_product = OrderProduct(order_id=order_id, product_id=product_id)
        db.session.add(order_product)
        db.session.commit()
        
        schema = OrderSchema()
        return jsonify({
            'message': f'Product {product_id} added to order {order_id}',
            'order': schema.dump(order)
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/orders/<int:order_id>/remove_product/<int:product_id>', methods=['DELETE'])
def remove_product_from_order(order_id, product_id):
    """Remove a product from an order"""
    try:
        # Verify order exists
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Verify product exists
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Check if product is in order
        order_product = OrderProduct.query.filter_by(
            order_id=order_id,
            product_id=product_id
        ).first()
        
        if not order_product:
            return jsonify({'error': 'Product not in this order'}), 404
        
        # Remove product from order
        db.session.delete(order_product)
        db.session.commit()
        
        schema = OrderSchema()
        return jsonify({
            'message': f'Product {product_id} removed from order {order_id}',
            'order': schema.dump(order)
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/orders/user/<int:user_id>', methods=['GET'])
def get_orders_by_user(user_id):
    """Get all orders for a user"""
    try:
        # Verify user exists
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get all orders for user
        orders = Order.query.filter_by(user_id=user_id).all()
        schema = OrderSchema(many=True)
        
        return jsonify({
            'user_id': user_id,
            'orders': schema.dump(orders)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/orders/<int:order_id>/products', methods=['GET'])
def get_products_in_order(order_id):
    """Get all products for an order"""
    try:
        # Verify order exists
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Get all products in order
        products = order.products
        schema = ProductSchema(many=True)
        
        return jsonify({
            'order_id': order_id,
            'products': schema.dump(products)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'API is running'}), 200


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database tables created!")
    
    app.run(debug=True, host='localhost', port=5000)
