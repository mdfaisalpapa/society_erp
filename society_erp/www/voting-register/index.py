import frappe


def get_context(context):
    context.no_cache = 1
    context.title = "Public Ballot Register"
    return context
