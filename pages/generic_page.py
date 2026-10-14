"""Customizations -> Generic List."""
from __future__ import annotations

from pages.customization_list_page import CustomizationListPage
from utils.constants import ROUTES


class GenericPage(CustomizationListPage):
    route = ROUTES["generic_list"]         # /generics
    entity = "Generic"
    add_button_name = "Add New Generic"
    name_label = "Generic Name"            # input id: genericName; optional "Therapeutic Class" (therapeuticClass)
