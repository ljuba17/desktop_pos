from PyQt6.QtWidgets import QDialog
from PyQt6 import uic
import os

class SelectCustomerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Učitavanje UI fajla
        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "select_customer.ui")
        uic.loadUi(ui_path, self)
        
        # Povezivanje događaja
        self.tipCombo.currentIndexChanged.connect(self.update_tip_edit)  # Ažuriranje tipEdit na osnovu izbora u tipCombo
        self.okButton.clicked.connect(self.accept)  # Dugme OK
        self.cancelButton.clicked.connect(self.on_cancel_clicked)  # Dugme Cancel

    def update_tip_edit(self):
        """Ažurira vrednost u tipEdit na osnovu izbora u tipCombo."""
        selected_text = self.tipCombo.currentText()
        tip_value = selected_text.split(' ')[0]  # Ekstrahujemo broj pre razmaka
        self.tipEdit.setText(tip_value)

    def get_selected_customer(self):
        """Vraća izabrani tip kupca iz ComboBox-a i dodatne unose."""
        tip_value = self.tipEdit.text()  # Broj iz tipEdit
        kupac_value = self.kupacTipEdit.text()  # Tekst iz kupacTipEdit
        return tip_value, kupac_value

    def on_cancel_clicked(self):
        """Obaveštava glavni prozor da treba obrisati podatke prilikom otkazivanja."""
        self.parent().tipEdit.clear()
        self.parent().kupacEdit.clear()
        self.reject()
