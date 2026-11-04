from django.contrib.auth import views as auth_views
from django.urls import path

from billing import views as billing
from core import views as core
from fbr import views as fbr

urlpatterns = [
    path("setup/", core.first_run, name="first_run"),
    path("login/", core.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),

    path("", billing.dashboard, name="dashboard"),
    path("invoices/", billing.invoice_list, name="invoice_list"),
    path("register/", billing.sales_register, name="sales_register"),
    path("register/export/", billing.sales_register_csv, name="sales_register_csv"),
    path("invoices/new/", billing.invoice_new, name="invoice_new"),
    path("invoices/start-number/", billing.set_start_number, name="set_start_number"),
    path("invoices/<int:pk>/", billing.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/print/", billing.invoice_print, name="invoice_print"),
    path("invoices/<int:pk>/debit-note/", billing.debit_note_new, name="debit_note_new"),
    path("invoices/<int:pk>/edit/", billing.invoice_edit, name="invoice_edit"),
    path("invoices/<int:pk>/delete/", billing.invoice_delete, name="invoice_delete"),
    path("invoices/<int:pk>/approve/", billing.invoice_approve, name="invoice_approve"),

    path("invoices/<int:pk>/send/", billing.invoice_send, name="invoice_send"),
    path("invoices/<int:pk>/found/", billing.invoice_found, name="invoice_found"),
    path("invoices/<int:pk>/not-found/", billing.invoice_not_found, name="invoice_not_found"),

    path("fbr/", fbr.setup, name="fbr_setup"),
    path("fbr/token/", fbr.save_token, name="fbr_save_token"),
    path("fbr/scenarios/", fbr.save_scenarios, name="fbr_save_scenarios"),
    path("fbr/test/", fbr.test_connection, name="fbr_test"),
    path("fbr/download/", fbr.download_lists, name="fbr_download"),
    path("fbr/rates/", fbr.rate_lookup, name="fbr_rates"),
    path("fbr/log/<int:pk>/", fbr.log_detail, name="fbr_log"),
    path("fbr/mode/", fbr.switch_mode, name="fbr_mode"),
    path("fbr/lookups/", fbr.lookups, name="fbr_lookups"),
    path("fbr/customers/<int:pk>/check/", fbr.check_customer, name="fbr_check_customer"),

    path("products/", core.product_list, name="product_list"),
    path("products/new/", core.product_edit, name="product_new"),
    path("products/<int:pk>/", core.product_edit, name="product_edit"),
    path("customers/", core.customer_list, name="customer_list"),
    path("customers/new/", core.customer_edit, name="customer_new"),
    path("customers/<int:pk>/", core.customer_edit, name="customer_edit"),
    path("company/", core.company_edit, name="company_edit"),
    path("registration/", core.registration, name="registration"),
]
