import frappe


def get_context(context):
    # Public landing page: intentionally does not require login.
    context.no_cache = 1
    context.title = "Kendriya Vihar Chennai Phase III Apartment Owners’ Association"
    context.show_sidebar = False
    return context
