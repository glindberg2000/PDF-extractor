from django import forms


class TransactionCSVForm(forms.Form):
    csv_file = forms.FileField(help_text="Upload a CSV file containing transactions.")
