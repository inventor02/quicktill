# -*- coding: utf-8 -*-

# When this module is loaded, 'configname' is set to the configuration
# name requested on the command line.  The module should define
# 'configurations' to be a dict indexed by configuration names.

import quicktill.extras
import quicktill.keyboard
import quicktill.pdrivers
import quicktill.ui
import quicktill.stockterminal
import quicktill.stocktype
import quicktill.usestock
import quicktill.modifiers
import quicktill.localutils
import quicktill.tillconfig
import quicktill.user
from decimal import Decimal, ROUND_UP
from contextlib import nullcontext
from collections import defaultdict

# Payment methods — ensure drivers are loaded
import quicktill.cash
import quicktill.squareterminal


# Secret stores
# quicktill.secretstore.Secrets(
#     'square-sandbox', b'')
# quicktill.secretstore.Secrets(
#     'square-production', b'')


# Declare the modifiers available to the till.  This is site-specific
# because modifiers refer to things like departments and stock types
# that are set up in the database.  Once declared, modifiers are added
# to buttons and stock lines entries in the database.

class Case(quicktill.modifiers.SimpleModifier):
    """Case modifier.

    When used with a stock line, checks that the item is Club Mate,
    sets the serving size to 20 and multiplies the price by 20.
    """
    def mod_stockline(self, stockline, sale):
        st = sale.stocktype
        if st.manufacturer != 'Club Mate':
            raise quicktill.modifiers.Incompatible(
                f"The {self.name} modifier can only be used with "
                "Club Mate.")
        if st.name == "Regular 330ml":
            caseqty = 24
        else:
            caseqty = 20
        # There may not be a price at this point
        if sale.price:
            sale.price = sale.price * caseqty
        sale.qty = sale.qty * caseqty
        sale.description = f"{st} case of {caseqty}"


class Half(quicktill.modifiers.SimpleModifier):
    """Half pint modifier.

    When used with a stock line, checks that the item is sold in pints
    and then halves the serving size and price.
    """
    def mod_stockline(self, stockline, sale):
        if sale.stocktype.unit.name == 'pint' \
           or (sale.stocktype.unit.name == 'ml'
               and sale.stocktype.unit.base_units_per_sale_unit == 568):
            # There may not be a price at this point
            if sale.price:
                sale.price = sale.price / 2
            sale.qty = sale.qty * Decimal("0.5")
            sale.description = f"{sale.stocktype} half pint"
            return
        raise quicktill.modifiers.Incompatible(
            f"The {self.name} modifier can only be used with stock "
            "that is sold in pints.")


class Mixer(quicktill.modifiers.SimpleModifier):
    """Mixers modifier.

    When used with a stockline, checks that the stock is sold in ml
    and priced in pints (568ml), sets the quantity to 100ml and the
    sale price to £0.70.
    """
    def mod_stockline(self, stockline, sale):
        if sale.stocktype.unit.name != 'ml' \
           or sale.stocktype.unit.base_units_per_sale_unit != 568:
            raise quicktill.modifiers.Incompatible(
                f"The {self.name} modifier can only be used with soft drinks.")
        if sale.price:
            sale.price = Decimal("0.70")
        sale.qty = Decimal("100.0")
        sale.description = f"{sale.stocktype} mixer"


class Carton(quicktill.modifiers.SimpleModifier):
    """1l Carton modifier.

    When used with a stockline, checks that the stock is sold in ml
    and priced in pints (568ml), sets the quantity to 1000ml and the
    sale price to £3.00.
    """
    def mod_stockline(self, stockline, sale):
        if sale.stocktype.unit.name != 'ml' \
           or sale.stocktype.unit.base_units_per_sale_unit != 568:
            raise quicktill.modifiers.Incompatible(
                f"The {self.name} modifier can only be used with soft drinks.")
        if sale.price:
            sale.price = Decimal("3.00")
        sale.qty = Decimal("1000.0")
        sale.description = f"{sale.stocktype} carton"


class Double(quicktill.modifiers.SimpleModifier):
    """Double spirits modifier.

    When used with a stock line, checks that the item is sold in 25ml
    or 50ml measures and then doubles the serving size and price.
    """
    def mod_stockline(self, stockline, sale):
        if sale.stocktype.unit.name not in ('25ml', '50ml'):
            raise quicktill.modifiers.Incompatible(
                f"The {self.name} modifier can only be used with spirits.")
        # There may not be a price at this point
        if sale.price:
            sale.price = sale.price * 2
        sale.qty = sale.qty * 2
        sale.description = f"{sale.stocktype} double " \
            f"{sale.stocktype.unit.name}"


class Wine(quicktill.modifiers.BaseModifier):
    """Wine serving modifier.

    When used with stocklines, checks that the stockline is a
    continuous stockline selling stock priced per 750ml in department
    90 (wine).  Adjusts the serving size and price appropriately.

    When used with price lookups, checks that the PLU department is 90
    (wine) and then selects the appropriate alternative price; small
    is alt price 1, large is alt price 3.
    """
    def __init__(self, name, size, text, field, extra):
        super().__init__(name)
        self.size = size
        self.text = text
        self.field = field
        self.extra = extra

    def mod_stockline(self, stockline, sale):
        if stockline.linetype != "continuous" \
           or (stockline.stocktype.unit.name != 'ml') \
           or (stockline.stocktype.unit.base_units_per_sale_unit != 750) \
           or (stockline.stocktype.dept_id != 90):
            raise quicktill.modifiers.Incompatible(
                "This modifier can only be used with wine.")
        sale.qty = self.size
        sale.description = f"{stockline.stocktype} {self.text}"
        if sale.price:
            sale.price = (self.size / Decimal("750.0") * sale.price)\
                .quantize(Decimal("0.1"), rounding=ROUND_UP)\
                .quantize(Decimal("0.10"))
            sale.price += self.extra

    def mod_plu(self, plu, sale):
        if plu.dept_id != 90:
            raise quicktill.modifiers.Incompatible(
                "This modifier can only be used with wine.")
        price = getattr(plu, self.field)
        if not price:
            raise quicktill.modifiers.Incompatible(
                f"The {plu.description} price lookup does not have "
                f"{self.field} set.")
        sale.price = price
        sale.description = plu.description + " " + self.text


Wine("Small", Decimal("125.0"), "125ml glass", "altprice1", Decimal("0.00"))
Wine("Medium", Decimal("175.0"), "175ml glass", "altprice2", Decimal("0.00"))
Wine("Large", Decimal("250.0"), "250ml glass", "altprice3", Decimal("0.00"))
Wine("Wine Bottle", Decimal("750.0"), "75cl bottle", "price", Decimal("0.00"))


# Suggested sale price algorithm

# We are passed a StockType (from which we can get manufacturer, name,
# department, abv and so on); StockUnit (size of container, eg. 72
# pints) and the ex-VAT cost of that unit
class PriceGuess(quicktill.stocktype.PriceGuessHook):
    @staticmethod
    def guess_price(stocktype, stockunit, cost):
        if stocktype.dept_id == 1:
            return markup(stocktype, stockunit, cost, Decimal("3.0"))
        if stocktype.dept_id == 2:
            return markup(stocktype, stockunit, cost, Decimal("2.3"))
        if stocktype.dept_id == 3:
            return markup(stocktype, stockunit, cost, Decimal("2.6"))
        if stocktype.dept_id == 4:
            return max(Decimal("2.50"),
                       markup(stocktype, stockunit, cost, Decimal("2.5")))
        if stocktype.dept_id == 5:
            return markup(stocktype, stockunit, cost, Decimal("2.0"))
        if stocktype.dept_id == 6:
            return markup(stocktype, stockunit, cost, Decimal("2.0"))
        if stocktype.dept_id == 13:
            return markup(stocktype, stockunit, cost, Decimal("2.3"))


def markup(stocktype, stockunit, cost, markup):
    return stocktype.department.vat.current.exc_to_inc(
        cost * markup / stockunit.size).\
        quantize(Decimal("0.1"), rounding=ROUND_UP)


quicktill.register.PercentageDiscount("Free", 100, permission_required=(
    "convert-to-free-drinks", "Convert a transaction to free drinks"))


# This is a very simple 'sample' app
def qr():
    if not quicktill.tillconfig.receipt_printer:
        quicktill.ui.infopopup(
            ["This till doesn't have a printer!"], title="Error")
        return
    with quicktill.tillconfig.receipt_printer as p:
        p.printline("\tWelcome to EMF!", colour=1)
        p.printline()
        p.printqrcode(bytes("https://bar.emf.camp/", "utf-8"))
        p.printline()
        p.printline("\tVisit")
        p.printline()
        p.printline("\tbar.emf.camp", colour=1)
        p.printline()
        p.printline("\tfor the price list")


def appsmenu():
    menu = [
        ("1", "Refusals log", quicktill.extras.refusals, ()),
        ("2", "QR code print", qr, ()),
    ]
    quicktill.ui.keymenu(menu, title="Apps")


std = {
    'database': 'dbname=emfcamp',
}


# Print to a locally-attached receipt printer
localprinter = {
    'printer': quicktill.pdrivers.autodetect_printer([
        ("/dev/epson-tm-t20",
         quicktill.pdrivers.Epson_TM_T20_driver(80), True),
        ("/dev/epson-tm-t20ii",
         quicktill.pdrivers.Epson_TM_T20_driver(80), True),
        ("/dev/aures-odp-333",
         quicktill.pdrivers.Aures_ODP_333_driver(), False),
        ("/dev/epson-tm-u220",
         quicktill.pdrivers.Epson_TM_U220_driver(76, has_cutter=True), False),
        ("/dev/lp0",
         quicktill.pdrivers.Epson_TM_U220_driver(76, has_cutter=True), True),
    ]),
}

# Label paper definitions
label11356 = (252, 118)
label99015 = (198, 154)
labelprinter = {
    'labelprinters': [
        quicktill.pdrivers.cupsprinter(
            "DYMO_LabelWriter_450",
            driver=quicktill.pdrivers.pdf_page(pagesize=label99015),
            description="DYMO label printer"),
    ],
}

# These keys are used by the register and stock terminal pages if they
# haven't already found a use for a keypress
register_hotkeys = quicktill.localutils.register_hotkeys(appsmenu=appsmenu)

# After this configuration file is read, the code in quicktill/till.py
# simply looks for configurations[configname]

configurations = defaultdict(lambda: dict(std))


def cf(n):
    return nullcontext(configurations[n])


with cf("default") as c:
    c.update({
        'description': "Stock-control terminal, default user is unprivileged",
        'firstpage': lambda: quicktill.stockterminal.page(
            register_hotkeys, ["Bar"]),
    })
    c.update(labelprinter)

with cf("mainbar-noprinter") as c:
    c.update({
        'description': "Main bar (no printer)",
        'hotkeys': quicktill.localutils.global_hotkeys(register_hotkeys),
        'keyboard': quicktill.localutils.keyboard(
            13, 6, line_base=1, maxwidth=16),
        'keyboard_right': quicktill.localutils.keyboard_rhpanel(
            "CASH", "SQUARE"),
    })
    c.update(quicktill.localutils.activate_register_with_usertoken(
        register_hotkeys))
    c.update(labelprinter)

configurations["mainbar"] = dict(configurations["mainbar-noprinter"])
with cf("mainbar") as c:
    c["description"] = "Main bar (with receipt printer)"
    c.update(localprinter)

with cf("cybar-noprinter") as c:
    c.update({
        'description': "Cybar (no printer)",
        'hotkeys': quicktill.localutils.global_hotkeys(
            register_hotkeys, stockterminal_location=["Null Sector"]),
        'keyboard': quicktill.localutils.keyboard(
            13, 6, line_base=201, maxwidth=16),
        'keyboard_right': quicktill.localutils.keyboard_rhpanel(
            "CASH", "SQUARE"),
    })
    c.update(quicktill.localutils.activate_register_with_usertoken(
        register_hotkeys))
    # No label printer at Null Sector bar

configurations["cybar"] = dict(configurations["cybar-noprinter"])
with cf("cybar") as c:
    c["description"] = "Cybar (with receipt printer)"
    c.update(localprinter)

with cf("stockterminal-mainbar") as c:
    c['description'] = "Stock-control terminal with card reader for main bar"
    c.update(quicktill.localutils.activate_stockterminal_with_usertoken(
        register_hotkeys))
    c.update(labelprinter)

with cf("stockterminal-cybar") as c:
    c['description'] = "Stock-control terminal with card reader for cybar"
    c.update(quicktill.localutils.activate_stockterminal_with_usertoken(
        register_hotkeys, ["Null Sector"]))
    # No label printer at Null Sector bar
