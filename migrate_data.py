import sys
from app import create_app
from models import db, User, Sponsor, Driver, StoreSettings, CartItem, DriverSponsorAssociation, Role
from sqlalchemy.exc import IntegrityError

# --- CONFIGURATION ---
DEFAULT_SPONSOR_ID = 6 
# --- END CONFIGURATION ---

app = create_app()

def migrate_driver_data(default_sponsor_id):
    """
    Finds all valid drivers, reads their old point totals, and creates a new
    DriverSponsorAssociation record to link them to the default sponsor.
    """
    print("Migrating driver points and associations...")
    
    # --- Start of Fix ---
    # This query now joins User and Driver to ensure we only get valid drivers
    # who have a profile in both tables.
    drivers_to_migrate = db.session.query(
        User.USER_CODE, User.POINTS
    ).join(
        Driver, User.USER_CODE == Driver.DRIVER_ID
    ).filter(
        User.USER_TYPE == Role.DRIVER
    ).all()
    # --- End of Fix ---
    
    migrated_count = 0
    for driver_code, old_points in drivers_to_migrate:
        existing_assoc = DriverSponsorAssociation.query.get((driver_code, default_sponsor_id))
        if existing_assoc:
            print(f"  - Association for driver {driver_code} already exists. Skipping.")
            continue

        new_association = DriverSponsorAssociation(
            driver_id=driver_code,
            sponsor_id=default_sponsor_id,
            points=old_points or 0
        )
        db.session.add(new_association)
        migrated_count += 1
        print(f"  - Migrating Driver {driver_code} with {old_points} points.")

    if migrated_count > 0:
        try:
            db.session.commit()
            print(f"✅ Successfully migrated {migrated_count} valid drivers.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error migrating drivers: {e}")
    else:
        print("No new valid drivers needed migration.")


def migrate_sponsor_settings():
    """
    Creates default store settings for all existing sponsors who don't have one.
    """
    print("\nCreating default store settings for sponsors...")
    
    sponsors = Sponsor.query.all()
    created_count = 0
    for sponsor in sponsors:
        existing_settings = StoreSettings.query.filter_by(sponsor_id=sponsor.SPONSOR_ID).first()
        if existing_settings:
            print(f"  - Settings for sponsor {sponsor.SPONSOR_ID} already exist. Skipping.")
            continue
            
        new_settings = StoreSettings(
            sponsor_id=sponsor.SPONSOR_ID,
            ebay_category_id='2984',
            point_ratio=10
        )
        db.session.add(new_settings)
        created_count += 1
        print(f"  - Creating settings for Sponsor {sponsor.SPONSOR_ID}.")

    if created_count > 0:
        try:
            db.session.commit()
            print(f"✅ Successfully created settings for {created_count} sponsors.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating sponsor settings: {e}")
    else:
        print("No new sponsor settings needed.")


def migrate_cart_items(default_sponsor_id):
    """
    Updates all existing cart items to be associated with the default sponsor.
    """
    print("\nUpdating existing cart items...")
    
    items_to_update = CartItem.query.filter(CartItem.sponsor_id.is_(None)).all()
    
    if not items_to_update:
        print("No cart items needed updating.")
        return

    for item in items_to_update:
        item.sponsor_id = default_sponsor_id
        print(f"  - Updating cart item {item.id} for user {item.user_id}.")
    
    try:
        db.session.commit()
        print(f"✅ Successfully updated {len(items_to_update)} cart items.")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating cart items: {e}")


def main():
    with app.app_context():
        default_sponsor = db.session.get(Sponsor, DEFAULT_SPONSOR_ID)
        if not default_sponsor:
            print(f"FATAL ERROR: The default sponsor with USER_CODE {DEFAULT_SPONSOR_ID} could not be found.")
            print("Please check the ID and try again.")
            sys.exit(1)
        
        print("--- Starting Data Migration ---")
        print(f"Using default sponsor: {default_sponsor.ORG_NAME} (ID: {DEFAULT_SPONSOR_ID})")
        
        migrate_driver_data(DEFAULT_SPONSOR_ID)
        migrate_sponsor_settings()
        migrate_cart_items(DEFAULT_SPONSOR_ID)
        
        print("\n--- Data Migration Complete ---")

if __name__ == '__main__':
    main()