import frappe

def after_install():
    """Runs automatically when the society_erp app is installed on a site."""
    # 1. Get the site's default company and its abbreviation
    company = frappe.defaults.get_global_default("company")
    if not company:
        return  # Skip setup if no company has been created on the site yet
        
    company_abbr = frappe.db.get_value("Company", company, "abbr")
    
    # 2. Safely create or fetch the Reserve Accounts
    sinking_acc = get_or_create_account("Sinking Fund", company, company_abbr)
    corpus_acc = get_or_create_account("Corpus Fund", company, company_abbr)
    emergency_acc = get_or_create_account("Emergency Fund", company, company_abbr)
    
    # 3. Create the Sales Taxes and Charges Template
    template_name = create_tax_template(company, sinking_acc, corpus_acc, emergency_acc)
    
    # 4. Map it to the Global Society ERP Settings
    map_to_settings(template_name)
    create_bot_user_and_role()

def get_or_create_account(base_name, company, abbr):
    """Dynamically finds the Liability group and creates the account if missing."""
    full_account_name = f"{base_name} - {abbr}"
    
    if frappe.db.exists("Account", full_account_name):
        return full_account_name
        
    # Search for a suitable Parent Account (Reserves or generic Liabilities)
    parent = frappe.db.get_value("Account", {"company": company, "is_group": 1, "account_name": ["like", "%Reserves%Surplus%"]})
    if not parent:
        parent = frappe.db.get_value("Account", {"company": company, "is_group": 1, "account_name": ["like", "%Liabilities%"]})
    if not parent:
        parent = frappe.db.get_value("Account", {"company": company, "is_group": 1, "root_type": "Liability"})
        
    if parent:
        acc = frappe.get_doc({
            "doctype": "Account",
            "account_name": base_name,
            "parent_account": parent,
            "company": company,
            "is_group": 0,
            "account_type": "Equity" 
        })
        acc.insert(ignore_permissions=True)
        return acc.name
        
    return None

def create_tax_template(company, sinking_acc, corpus_acc, emergency_acc):
    """Generates the 10% Levy Template mapped to the dynamic accounts."""
    template_name = "Standard Infrastructure & Asset Levy"
    
    if frappe.db.exists("Sales Taxes and Charges Template", template_name):
        return template_name
        
    if not (sinking_acc and corpus_acc and emergency_acc):
        return None # Failsafe if accounts couldn't be created
        
    template = frappe.get_doc({
        "doctype": "Sales Taxes and Charges Template",
        "title": template_name,
        "company": company,
        "taxes": [
            {
                "charge_type": "On Net Total",
                "account_head": sinking_acc,
                "rate": 6.0,
                "description": "Sinking Fund (60% of Levy)"
            },
            {
                "charge_type": "On Net Total",
                "account_head": corpus_acc,
                "rate": 3.0,
                "description": "Corpus Fund (30% of Levy)"
            },
            {
                "charge_type": "On Net Total",
                "account_head": emergency_acc,
                "rate": 1.0,
                "description": "Emergency Fund (10% of Levy)"
            }
        ]
    })
    template.insert(ignore_permissions=True)
    return template.name

def map_to_settings(template_name):
    """Sets the newly created template as the global default."""
    if not template_name:
        return
        
    # Ensure the single DocType record exists
    if not frappe.db.exists("Society ERP Settings", "Society ERP Settings"):
        settings = frappe.new_doc("Society ERP Settings")
    else:
        settings = frappe.get_doc("Society ERP Settings")
        
    settings.infrastructure_asset_depreciation_template = template_name
    settings.save(ignore_permissions=True)


def create_bot_user_and_role():
    role_name = "Society Bot"
    bot_email = "botuser@society.local" # Change to your preferred default bot email
    
    # 1. Create the Role if it doesn't exist
    if not frappe.db.exists("Role", role_name):
        role = frappe.get_doc({
            "doctype": "Role",
            "role_name": role_name,
            # Bots generally do not need Desk access unless strictly required by your API structure
            "desk_access": 0 
        })
        role.insert(ignore_permissions=True)
        
    # 2. Create the User if it doesn't exist
    if not frappe.db.exists("User", bot_email):
        bot_user = frappe.get_doc({
            "doctype": "User",
            "email": bot_email,
            "first_name": "Telegram",
            "last_name": "Bot",
            "send_welcome_email": 0,
            "user_type": "System User" 
        })
        bot_user.insert(ignore_permissions=True)
        
        # 3. Assign the new Role to the User
        bot_user.add_roles(role_name)
        
        # 4. Generate API Keys automatically
        bot_user.generate_keys()
        
        # We must commit the transaction to read the unhashed secret key
        frappe.db.commit() 
        
        api_key = bot_user.api_key
        api_secret = bot_user.get_password('api_secret')
        
        # 5. Print the credentials to the console during installation
        print("\n" + "="*40)
        print("🤖 SOCIETY BOT ACCOUNT CREATED")
        print(f"User: {bot_email}")
        print(f"API Key: {api_key}")
        print(f"API Secret: {api_secret}")
        print("SAVE THESE CREDENTIALS FOR YOUR TELEGRAM BOT!")
        print("="*40 + "\n")
