from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QDateEdit, QPushButton
)
from PyQt6.QtCore import QDate

class KepStampaDijalog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Izbor datuma za štampu")

        layout = QVBoxLayout()

        # Datum OD
        layout.addWidget(QLabel("Od datuma:"))
        self.oddatumaEdit = QDateEdit()
        self.oddatumaEdit.setCalendarPopup(True)
        self.oddatumaEdit.setDate(QDate.currentDate())
        layout.addWidget(self.oddatumaEdit)

        # Datum DO
        layout.addWidget(QLabel("Do datuma:"))
        self.dodatumaEdit = QDateEdit()
        self.dodatumaEdit.setCalendarPopup(True)
        self.dodatumaEdit.setDate(QDate.currentDate())
        layout.addWidget(self.dodatumaEdit)

        # Dugmad
        btn_layout = QHBoxLayout()
        self.btnStampa = QPushButton("Štampa")
        self.btnOdustani = QPushButton("Odustani")
        btn_layout.addWidget(self.btnStampa)
        btn_layout.addWidget(self.btnOdustani)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        # Signali
        self.btnStampa.clicked.connect(self.accept)
        self.btnOdustani.clicked.connect(self.reject)

    def get_datumi(self):
        return self.oddatumaEdit.date().toPyDate(), self.dodatumaEdit.date().toPyDate()

    