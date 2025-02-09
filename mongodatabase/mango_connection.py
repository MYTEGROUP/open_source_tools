#src/mongodatabase/mango_connection.py

import stripe
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime
from helpers.Manage_Json_files import JSONManager

# Load environment variables once
load_dotenv()

# MongoDB configuration
mongo_uri = os.getenv('MONGO_URI')
mongo_db_name = os.getenv('MONGO_DB_NAME')

# Collections
users_collection_name = 'users'
contacts_collection_name = 'contacts'
notes_collection_name = 'notes'
meetings_collection_name = 'Meetings'

def save_meeting_data_to_mongo(meeting_data):
    """Save meeting data to MongoDB and ensure schema consistency."""
    db = get_database()
    meetings_collection = db[meetings_collection_name]

    # Required schema fields in the exact order
    required_fields = [
        "meeting_title", "date", "start_time", "end_time", "duration",
        "full_transcript", "summary", "tokens_used"
    ]

    # Ensure that the meeting_data matches the required schema
    for field in required_fields:
        if field not in meeting_data:
            JSONManager.log_event(
                "save_meeting_data_to_mongo_error", f"Missing field '{field}' in meeting data."
            )
            return False

    # Insert or update meeting data in MongoDB
    try:
        filter_query = {"meeting_title": meeting_data["meeting_title"], "date": meeting_data["date"]}
        update_query = {"$set": meeting_data}
        result = meetings_collection.update_one(filter_query, update_query, upsert=True)

        # Log the operation with more details on insert or update
        if result.upserted_id:
            JSONManager.log_event(
                "save_meeting_data_to_mongo",
                f"Meeting '{meeting_data['meeting_title']}' created with ID {result.upserted_id}."
            )
            return True
        elif result.modified_count > 0:
            JSONManager.log_event(
                "save_meeting_data_to_mongo",
                f"Meeting '{meeting_data['meeting_title']}' updated. {result.modified_count} document(s) modified."
            )
            return True
        else:
            JSONManager.log_event(
                "save_meeting_data_to_mongo",
                f"No changes detected for meeting '{meeting_data['meeting_title']}'."
            )
            return True

    except Exception as e:
        JSONManager.log_event("save_meeting_data_to_mongo_error", f"Error saving meeting to MongoDB: {e}")
        return False


def get_mongo_client():
    """Return a MongoDB client instance."""
    if not mongo_uri:
        raise ValueError("MongoDB URI not found in environment variables.")

    try:
        client = MongoClient(mongo_uri)
        client.admin.command('ping')  # Ensure connection is established
    except Exception as e:
        raise ConnectionError(f"Failed to connect to MongoDB: {str(e)}")

    return client


def get_database(db_name=None):
    """Return a MongoDB database instance, connecting only when necessary."""
    client = get_mongo_client()
    db_name = db_name or mongo_db_name
    return client[db_name]


def setup_crm_collections():
    """Ensure that the CRM collections are created and indexed correctly."""
    db = get_database()
    contacts_collection = db[contacts_collection_name]
    notes_collection = db[notes_collection_name]

    # Remove unique index on 'contact_id' if it exists
    if "contact_id_1" in contacts_collection.index_information():
        contacts_collection.drop_index("contact_id_1")

    # Remove unique index on 'note_id' if it exists
    if "note_id_1" in notes_collection.index_information():
        notes_collection.drop_index("note_id_1")

    # Create a compound unique index on 'user_id' and 'email' to prevent duplicate emails per user
    contacts_collection.create_index(
        [("user_id", 1), ("email", 1)],
        unique=True,
        name="user_email_unique"
    )

    # Create text index for search fields
    contacts_collection.create_index(
        [("name", "text"), ("email", "text"), ("company", "text")],
        name="search_text_index"
    )

    # Create index on 'contact_id' in notes_collection for efficient querying
    notes_collection.create_index("contact_id")


def update_access_key(email):
    """Update the access_key to True for the given email."""
    try:
        db = get_database()
        users_collection = db['users']
        users_collection.update_one(
            {"email": email},
            {"$set": {"access_key": True}}
        )
        return {"status": "success", "message": "Access key updated to True."}
    except Exception as e:
        return {"status": "error", "message": f"An error occurred while updating access key: {str(e)}"}

def get_contacts_from_mongo(user_id):
    """
    Retrieves all contacts associated with the given user_id.
    """
    try:
        db = get_database()
        contacts_collection = db[contacts_collection_name]
        contacts = list(contacts_collection.find({"user_id": user_id}))
        JSONManager.log_event("get_contacts_from_mongo", f"Retrieved {len(contacts)} contacts for user {user_id}.")
        return contacts
    except Exception as e:
        JSONManager.log_event("get_contacts_from_mongo_error", f"Error retrieving contacts: {e}")
        return []


def create_new_contact_in_mongo(user_id, contact_data):
    """
    Function to save the new contact information in MongoDB.
    """
    try:
        db = get_database()
        contacts_collection = db['contacts']
        contact_data['user_id'] = user_id
        result = contacts_collection.insert_one(contact_data)
        contact_data['_id'] = str(result.inserted_id)  # Convert ObjectId to string
        return contact_data
    except Exception as e:
        print(f"Error creating contact: {str(e)}")
        return None


def get_user_id_from_json():
    """
    Retrieves the user_id from user_info.json.
    """
    try:
        user_info = JSONManager.read_json_file('user_info.json')
        user_id = user_info.get('user_id')
        JSONManager.log_event("get_user_id_from_json", f"Retrieved user_id: {user_id}.")
        return user_id
    except Exception as e:
        JSONManager.log_event("get_user_id_from_json_error", f"Error retrieving user_id: {e}")
        return None

def update_access_key_from_json():
    """Retrieve email from 'user_info.json' and update access key in MongoDB."""
    user_info = JSONManager.read_json_file('user_info.json')
    email = user_info.get('email')

    if not email:
        JSONManager.log_event("update_access_key_from_json", "No email found in user_info.json.")
        return {"status": "error", "message": "Email not found in user_info.json"}

    result = update_access_key(email)

    if result['status'] == 'success':
        JSONManager.log_event("update_access_key_from_json", "User's access key has been successfully updated.")
    else:
        JSONManager.log_event("update_access_key_from_json", f"Failed to update user's access key: {result['message']}")

    return result


def get_access_key_from_db(email):
    """Retrieve the access_key and subscription status for the given email."""
    try:
        db = get_database()
        users_collection = db['users']
        user = users_collection.find_one({"email": email}, {"access_key": 1, "is_subscribed": 1, "_id": 0})

        if user:
            return user.get("access_key", False), user.get("is_subscribed", False)
        else:
            return False, False
    except Exception as e:
        JSONManager.log_event("get_access_key_from_db", f"An error occurred while retrieving access_key: {str(e)}")
        return False, False


def update_user_subscription(email, is_subscribed, subscription_type=None, subscription_date=None, product_title=None,
                             product_id=None, stripe_customer_id=None, default_payment_method=None, subscription_end_date=None):
    """Update user subscription status in MongoDB."""
    try:
        db = get_database()
        users_collection = db['users']

        # Prepare the data to update
        update_data = {
            "is_subscribed": is_subscribed,
            "subscription_end_date": subscription_end_date
        }

        # Optionally add the other fields if they are provided
        if subscription_type is not None:
            update_data["subscription_type"] = subscription_type
        if subscription_date is not None:
            update_data["subscription_date"] = subscription_date
        if product_title is not None:
            update_data["product_title"] = product_title
        if product_id is not None:
            update_data["product_id"] = product_id
        if stripe_customer_id is not None:
            update_data["stripe_customer_id"] = stripe_customer_id
        if default_payment_method is not None:
            update_data["default_payment_method"] = default_payment_method

        # Perform the update using the email as the identifier
        result = users_collection.update_one(
            {"email": email},
            {"$set": update_data}
        )

        if result.matched_count > 0:
            JSONManager.log_event("update_user_subscription", f"Subscription status updated for email {email} with data: {update_data}.")
        else:
            JSONManager.log_event("update_user_subscription", f"No user found with email {email}.", "failure")

    except Exception as e:
        JSONManager.log_event("update_user_subscription", f"Error updating subscription status for email {email}: {str(e)}")


def validate_subscription_status(email):
    """Check the current subscription status with Stripe and update MongoDB."""
    db = get_database()
    users_collection = db['users']

    user = users_collection.find_one({"email": email})
    if not user or not user.get('stripe_customer_id'):
        return False

    customer_id = user['stripe_customer_id']

    try:
        # Fetch the customer's subscriptions from Stripe
        subscriptions = stripe.Subscription.list(customer=customer_id, status='all')
        if subscriptions.data:
            # Check if there's an active subscription
            active_subscription = any(sub['status'] == 'active' for sub in subscriptions.data)
            subscription_end_date = datetime.fromtimestamp(subscriptions.data[0]['current_period_end']).strftime('%Y-%m-%d')
            current_date = datetime.now().strftime('%Y-%m-%d')

            # Update the user's subscription status in MongoDB
            users_collection.update_one(
                {"email": email},
                {"$set": {
                    "is_subscribed": active_subscription and (current_date <= subscription_end_date),
                    "subscription_end_date": subscription_end_date
                }}
            )
            return active_subscription
        else:
            # No subscriptions found, mark as unsubscribed
            users_collection.update_one(
                {"email": email},
                {"$set": {"is_subscribed": False}}
            )
            return False
    except Exception as e:
        JSONManager.log_event("validate_subscription_status", f"Failed to validate subscription status: {str(e)}")
        return False


def check_and_update_subscription_status(email):
    """Check the user's subscription status for a specific product from Stripe and update MongoDB accordingly."""
    db = get_database()
    users_collection = db['users']

    user = users_collection.find_one({"email": email})
    if not user:
        return False, "No user record found in the database."

    customer_id = user.get('stripe_customer_id')
    expected_product_id = user.get('product_id')  # Assuming the product ID is stored in MongoDB
    JSONManager.log_event("check_access_key",
                          f"user {email} has customer ID {customer_id} and product ID: {expected_product_id}")  # Log the message for debugging purposes

    # Handle cases where there's no Stripe customer ID
    if not customer_id:
        users_collection.update_one(
            {"email": email},
            {"$set": {"is_subscribed": False}}
        )
        JSONManager.log_event("check_customer_id_stripe",
                              f"No Stripe customer ID found for this user in the database. Subscription status set to unsubscribed.")  # Log the message for debugging purposes

        return False, "No Stripe customer ID found for this user. Subscription status set to unsubscribed."

    if not expected_product_id:
        JSONManager.log_event("check_customer_id_stripe",
                              f"No product ID found for this user in the database.")  # Log the message for debugging purposes

        return False, "No product ID found for this user in the database."

    try:
        # Fetch the customer's subscriptions from Stripe
        subscriptions = stripe.Subscription.list(customer=customer_id, status='all')

        if not subscriptions.data:
            # No subscriptions found, mark as unsubscribed
            users_collection.update_one(
                {"email": email},
                {"$set": {"is_subscribed": False}}
            )
            return False, "No subscriptions found. Marked as unsubscribed."

        # Iterate through the subscriptions and check for a match
        for subscription in subscriptions.data:
            for item in subscription['items']['data']:
                if item['price']['product'] == expected_product_id:
                    is_active = subscription['status'] == 'active'
                    subscription_end_date = datetime.fromtimestamp(subscription['current_period_end']).strftime('%Y-%m-%d')

                    # Update the user's subscription status in MongoDB
                    update_user_subscription(
                        email=email,
                        is_subscribed=is_active,
                        subscription_type=subscription['plan']['nickname'],
                        subscription_date=datetime.fromtimestamp(subscription['current_period_start']).strftime('%Y-%m-%d'),
                        product_title=stripe.Product.retrieve(expected_product_id)['name'],
                        product_id=expected_product_id,
                        stripe_customer_id=customer_id,
                        default_payment_method=subscription['default_payment_method'],
                        subscription_end_date=subscription_end_date
                    )
                    JSONManager.log_event("check_customer_id_stripe",
                                          f"Subscription status updated for Customer ID {customer_id}.")  # Log the message for debugging purposes

                    return is_active, "Subscription status updated."

        # If no matching subscription is found, mark as unsubscribed
        users_collection.update_one(
            {"email": email},
            {"$set": {"is_subscribed": False}}
        )
        JSONManager.log_event("check_customer_id_stripe",
                              f"No matching subscription found for product ID {expected_product_id}. Marked as unsubscribed.")  # Log the message for debugging purposes

        return False, "No active subscriptions found for the specified product."

    except stripe.error.InvalidRequestError as e:
        # Handle case where the customer ID is invalid or has been deleted
        if "No such customer" in str(e):
            users_collection.update_one(
                {"email": email},
                {"$set": {"is_subscribed": False}}
            )
            return False, "No such customer found in Stripe. Subscription status set to unsubscribed."

        JSONManager.log_event("check_and_update_subscription_status", f"Failed to check subscription status: {str(e)}")
        return False, f"Error while checking subscription status: {str(e)}"

    except Exception as e:
        JSONManager.log_event("check_and_update_subscription_status", f"Failed to check subscription status: {str(e)}")
        return False, f"Error while checking subscription status: {str(e)}"
