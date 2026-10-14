"""Customizations -> Company List."""
from __future__ import annotations

from pages.customization_list_page import CustomizationListPage
from utils.constants import ROUTES


class CompanyPage(CustomizationListPage):
    route = ROUTES["company_list"]          # /companies
    entity = "Company"
    add_button_name = "Add New Company"
    name_label = "Company Name"             # input id: companyName
