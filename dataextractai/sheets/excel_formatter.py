"""Excel formatter for creating rich transaction reports with validation and charts."""

import pandas as pd
import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.chart import PieChart, Reference, BarChart
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import numpy as np
from typing import List, Dict, Optional
import os
from openpyxl.workbook.defined_name import DefinedName


class ExcelReportFormatter:
    """Creates rich Excel reports with validation, charts, and summaries."""

    def __init__(self):
        """Initialize the Excel formatter with styles."""
        self.header_fill = PatternFill(
            start_color="1F4E78", end_color="1F4E78", fill_type="solid"
        )
        self.header_font = Font(color="FFFFFF", bold=True)
        self.header_alignment = Alignment(horizontal="center", vertical="center")

        # Define column groups for different sheets
        self.raw_data_columns = [
            "transaction_date",
            "description",
            "amount",
            "file_path",
            "source",
            "transaction_type",
            "normalized_amount",
            "statement_start_date",
            "statement_end_date",
            "account_number",
            "transaction_id",
            "payee",
            "payee_confidence",
            "payee_reasoning",
            "category",
            "category_confidence",
            "category_reasoning",
            "suggested_new_category",
            "new_category_reasoning",
            "classification",
            "classification_confidence",
            "classification_reasoning",
            "tax_implications",
        ]

        self.clean_data_columns = [
            "transaction_date",
            "description",
            "normalized_amount",
            "payee",
            "payee_confidence",
            "category",
            "category_confidence",
            "suggested_new_category",
            "classification",
            "classification_confidence",
            "tax_implications",
        ]

        self.summary_columns = [
            "category",
            "total_amount",
            "transaction_count",
            "average_amount",
            "average_confidence",
        ]

    def create_report(
        self,
        data: pd.DataFrame,
        output_path: str,
        categories: list = None,
        classifications: list = None,
    ):
        """Create a complete Excel report with multiple sheets."""
        # Create workbook
        wb = openpyxl.Workbook()

        # Remove default sheet
        wb.remove(wb.active)

        # Create sheets
        self._create_raw_data_sheet(wb, data)
        self._create_clean_data_sheet(wb, data, categories, classifications)
        self._create_summary_sheet(wb, data)

        # Save workbook
        wb.save(output_path)

    def _create_raw_data_sheet(self, workbook, data):
        """Create the Raw Data sheet with original transaction data."""
        ws = workbook.create_sheet("Raw Data")

        # Filter columns and reorder
        df_raw = data[self.raw_data_columns].copy()

        # Write headers
        for col, header in enumerate(df_raw.columns, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = self.header_alignment

        # Write data
        for row in range(len(df_raw)):
            for col, value in enumerate(df_raw.iloc[row], 1):
                ws.cell(row=row + 2, column=col, value=value)

        # Auto-adjust column widths
        for col in range(1, len(df_raw.columns) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 15

        # Add filters
        ws.auto_filter.ref = f"A1:{get_column_letter(len(df_raw.columns))}1"

    def _create_clean_data_sheet(self, workbook, data, categories, classifications):
        """Create the Clean Data sheet with validation dropdowns."""
        ws = workbook.create_sheet("Clean Data")

        # Filter and reorder columns
        df_clean = data[self.clean_data_columns].copy()

        # Write headers
        for col, header in enumerate(df_clean.columns, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = self.header_alignment

        # Write data
        for row in range(len(df_clean)):
            for col, value in enumerate(df_clean.iloc[row], 1):
                ws.cell(row=row + 2, column=col, value=value)

        # Add data validation for categories and classifications
        if categories:
            # Create a hidden sheet for validation lists
            validation_sheet = workbook.create_sheet("_Validation")
            validation_sheet.sheet_state = "hidden"

            # Write categories to validation sheet
            for i, cat in enumerate(categories, 1):
                validation_sheet[f"A{i}"] = cat

            # Create validation using direct range reference
            cat_validation = DataValidation(
                type="list",
                formula1=f"'_Validation'!$A$1:$A${len(categories)}",
                allow_blank=True,
            )
            ws.add_data_validation(cat_validation)
            cat_col = df_clean.columns.get_loc("category") + 1
            cat_validation.add(
                f"{get_column_letter(cat_col)}2:{get_column_letter(cat_col)}{len(df_clean)+1}"
            )

        if classifications:
            # Write classifications to validation sheet
            for i, cls in enumerate(classifications, 1):
                validation_sheet[f"B{i}"] = cls

            # Create validation using direct range reference
            class_validation = DataValidation(
                type="list",
                formula1=f"'_Validation'!$B$1:$B${len(classifications)}",
                allow_blank=True,
            )
            ws.add_data_validation(class_validation)
            class_col = df_clean.columns.get_loc("classification") + 1
            class_validation.add(
                f"{get_column_letter(class_col)}2:{get_column_letter(class_col)}{len(df_clean)+1}"
            )

        # Auto-adjust column widths
        for col in range(1, len(df_clean.columns) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 15

        # Add filters
        ws.auto_filter.ref = f"A1:{get_column_letter(len(df_clean.columns))}1"

    def _create_summary_sheet(self, workbook, data):
        """Create the Summary sheet with totals and charts using formulas."""
        ws = workbook.create_sheet("Summary")

        # Find column indices from the clean data columns list
        category_col = get_column_letter(self.clean_data_columns.index("category") + 1)
        amount_col = get_column_letter(
            self.clean_data_columns.index("normalized_amount") + 1
        )
        confidence_col = get_column_letter(
            self.clean_data_columns.index("category_confidence") + 1
        )
        last_row = len(data) + 1

        # Write headers
        headers = [
            "Category",
            "Total Amount",
            "Transaction Count",
            "Average Amount",
            "Average Confidence",
        ]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = self.header_alignment

        # Get unique categories and ensure they're strings before sorting
        categories = sorted(
            str(cat) for cat in data["category"].unique() if pd.notna(cat)
        )

        # Write category rows with formulas
        for row, category in enumerate(categories, 2):
            # Category name
            ws.cell(row=row, column=1, value=category)

            # Total Amount (SUMIF)
            total_formula = f"=SUMIF('Clean Data'!{category_col}2:{category_col}{last_row},A{row},'Clean Data'!{amount_col}2:{amount_col}{last_row})"
            ws.cell(row=row, column=2, value=total_formula).number_format = (
                '"$"#,##0.00'
            )

            # Transaction Count (COUNTIF)
            count_formula = f"=COUNTIF('Clean Data'!{category_col}2:{category_col}{last_row},A{row})"
            ws.cell(row=row, column=3, value=count_formula)

            # Average Amount (AVERAGEIF)
            avg_amount_formula = f"=IF(C{row}>0,B{row}/C{row},0)"
            ws.cell(row=row, column=4, value=avg_amount_formula).number_format = (
                '"$"#,##0.00'
            )

            # Average Confidence (AVERAGEIF)
            avg_conf_formula = f"=AVERAGEIF('Clean Data'!{category_col}2:{category_col}{last_row},A{row},'Clean Data'!{confidence_col}2:{confidence_col}{last_row})"
            conf_cell = ws.cell(row=row, column=5, value=avg_conf_formula)
            conf_cell.number_format = "0.00%"

        # Create pie chart
        pie = PieChart()
        pie.title = "Expenses by Category"

        # Use direct references for chart data
        last_category_row = len(categories) + 1
        data_ref = Reference(ws, min_col=2, min_row=1, max_row=last_category_row)
        labels_ref = Reference(ws, min_col=1, min_row=2, max_row=last_category_row)
        pie.add_data(data_ref, titles_from_data=True)
        pie.set_categories(labels_ref)

        # Add chart to worksheet
        ws.add_chart(pie, "F2")

        # Auto-adjust column widths
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 15
