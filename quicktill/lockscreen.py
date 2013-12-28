from . import ui,keyboard,td
from .models import PopupLockScreenUser
from .version import version

def usersmenu(func):
    users=td.s.query(PopupLockScreenUser).order_by(PopupLockScreenUser.code).all()
    f=ui.tableformatter(' r l ')
    sl=[(ui.tableline(f,(u.code,u.name)),func,(u.code,)) for u in users]
    ui.menu(sl,title="Users",blurb="Choose a user and press Cash/Enter.")

class popup(ui.dismisspopup):
    def __init__(self):
        """
        If there is not already a lock popup on the current page, display one.

        """
        # Check down the stack of windows to see if any of them are
        # this popup or the UnlockPopup; exit if any of them are
        for p in ui.basicwin._focus.parents():
            if isinstance(p,popup): return
            if isinstance(p,UnlockPopup): return
        ui.dismisspopup.__init__(self,7,45,title="Screen Lock",
                                 colour=ui.colour_confirm)
        self.addstr(2,2,"Enter your code to lock:")
        self.addstr(4,2,"Press Manage Till to add or remove users.")
        self.codefield=ui.editfield(2,27,2,keymap={
                keyboard.K_CASH: (self.enter_key,None),
                keyboard.K_MANAGETILL: (editusers,None)})
        self.codefield.focus()
    def enter_key(self):
        if self.codefield.f=='': usersmenu(self.user_selected)
        user=td.s.query(PopupLockScreenUser).get(self.codefield.f)
        if user:
            self.dismiss()
            UnlockPopup(user)
        else:
            self.codefield.set("")
    def user_selected(self,code):
        self.codefield.set(code)
        self.enter_key()

class UnlockPopup(ui.basicpopup):
    def __init__(self,user):
        msg="This screen is locked by %s."%(user.name,)
        minwidth=len(msg)+4
        ui.basicpopup.__init__(self,7,max(45,minwidth),title="Screen Lock",
                               colour=ui.colour_confirm)
        self.code=user.code
        self.addstr(2,2,"This screen is locked by %s."%(user.name,))
        self.addstr(4,2,"Enter code to unlock: ")
        self.codefield=ui.editfield(4,24,2,keymap={
                keyboard.K_CASH: (self.enter_key,None)})
        self.codefield.focus()
    def enter_key(self):
        if self.codefield.f=='': usersmenu(self.user_selected)
        if self.codefield.f==self.code:
            self.dismiss()
        else:
            self.codefield.set("")
    def user_selected(self,code):
        self.codefield.set(code)
        self.enter_key()
    
class editusers(ui.listpopup):
    """
    A window showing the list of users for the lock screen.  Pressing
    Cancel on a line deletes the user.  Pressing Enter goes to the
    dialog for adding a new user.

    """
    def __init__(self):
        ulist=td.s.query(PopupLockScreenUser).order_by(PopupLockScreenUser.code).all()
        f=ui.tableformatter(' l l ')
        headerline=ui.tableline(f,["Code","Name"])
        lines=[ui.tableline(f,(u.code,u.name),userdata=u.code)
               for u in ulist]
        ui.listpopup.__init__(
            self,lines,title="Lock Screen Users",
            header=["Press Cancel to delete a code.  "
                    "Press Enter to add a new code.",
                    headerline])
    def keypress(self,k):
        if k==keyboard.K_CANCEL and self.s and len(self.s.dl)>0:
            line=self.s.dl.pop(self.s.cursor)
            self.s.redraw()
            u=td.s.query(PopupLockScreenUser).get(line.userdata)
            td.s.delete(u)
        elif k==keyboard.K_CASH:
            self.dismiss()
            adduser()
        else:
            ui.listpopup.keypress(self,k)

class adduser(ui.dismisspopup):
    def __init__(self):
        ui.dismisspopup.__init__(self,7,34,title="Add Lock Screen User",
                                 colour=ui.colour_input)
        self.addstr(2,2,"New code: ")
        self.addstr(3,2,"New user name:")
        self.codefield=ui.editfield(2,12,2,keymap={
                keyboard.K_CLEAR: (self.dismiss,None)})
        self.namefield=ui.editfield(4,2,30,keymap={
                keyboard.K_CASH: (self.enter,None)})
        ui.map_fieldlist([self.codefield,self.namefield])
        self.codefield.focus()
    def enter(self):
        if len(self.codefield.f)!=2:
            ui.infopopup(["The code must be two characters."],title="Error")
            return
        if len(self.namefield.f)<2:
            ui.infopopup(["You must provide a name."],title="Error")
            return
        if td.s.query(PopupLockScreenUser).get(self.codefield.f):
            ui.infopopup(["That code is already in use."],title="Error")
            return
        self.dismiss()
        td.s.add(PopupLockScreenUser(code=self.codefield.f,name=self.namefield.f))

class lockpage(ui.basicpage):
    def __init__(self):
        ui.basicpage.__init__(self)
        self.win.addstr(1,1,"This is quicktill version %s"%version)
        self.win.addstr(3,1,"This till is locked.")
        self.win.move(0,0)
        self.updateheader()
    def keypress(self,k):
        self.win.addstr(5,1,' '*30)
        if hasattr(k,'keycap'):
            self.win.addstr(5,1,k.keycap)
        else:
            self.win.addstr(5,1,unicode(k))
        self.win.move(0,0)
    def pagename(self):
        return "Lock"
    def deselect(self):
        # This page ceases to exist when it disappears.
        ui.basicpage.deselect(self)
        self.dismiss()
