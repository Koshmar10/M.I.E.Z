from django.urls import path

from .views import assistant, auth, employees, hr, inventory, it, legacy, notifications, reports, sales, workflows

urlpatterns = [
    # auth
    path('auth/login/', auth.LoginView.as_view(), name='login'),
    path('auth/logout/', auth.LogoutView.as_view(), name='logout'),
    path('auth/me/', auth.UserMeView.as_view(), name='user_me'),
    path('auth/change-password/', auth.ChangePasswordView.as_view(), name='change_password'),
    # employees
    path('departments/', employees.DepartmentListCreateView.as_view(), name='department_list_create'),
    path('departments/<int:id>/', employees.DepartmentDeleteView.as_view(), name='department_delete'),
    path('employees/', employees.EmployeeListView.as_view(), name='employee_list'),
    path('employees/<int:id>/', employees.EmployeeDetailView.as_view(), name='employee_detail'),
    path('employees/stats/', employees.EmployeeStatsView.as_view(), name='employee_stats'),
    # hr
    path('attendance/', hr.HrAttendanceView.as_view(), name='attendance_grid'),
    path('leave-requests/', hr.LeaveRequestListCreateView.as_view(), name='leave_request_list_create'),
    path('leave-requests/<int:id>/approve/', hr.LeaveRequestApproveView.as_view(), name='leave_request_approve'),
    path('leave-requests/<int:id>/reject/', hr.LeaveRequestRejectView.as_view(), name='leave_request_reject'),
    path('contracts/', hr.ContractListView.as_view(), name='contract_list'),
    path('contracts/<int:id>/', hr.ContractDetailView.as_view(), name='contract_detail'),
    path('payroll/', hr.PayrollListView.as_view(), name='payroll_list'),
    path('hr/upcoming-events/', hr.HrUpcomingEventsView.as_view(), name='hr_upcoming_events'),
    path('hr/dashboard/', hr.HrDashboardView.as_view(), name='hr_dashboard_kpis'),
    path('hr/ceo-summary/', hr.CeoHrSummaryView.as_view(), name='ceo_hr_summary'),
    path('hr/digest/generate/', hr.HrDigestGenerateView.as_view(), name='hr_digest_generate'),
    path('hr/latest-digest/', hr.LatestHrDigestView.as_view(), name='hr_latest_digest'),
    path('hr/run-insights-agent/', hr.RunInsightsAgentView.as_view(), name='run_insights_agent'),
    # it
    path('it/dashboard/', it.DashboardItView.as_view(), name='dashboard_data'),
    path('it/ticket-trend/', it.ItTicketTrendView.as_view(), name='it_ticket_trend'),
    path('it/technician-stats/', it.TechnicianStatsView.as_view(), name='it_technician_stats'),
    path('it/assets/', it.AssetListCreateView.as_view(), name='asset_list_create'),
    path('it/assets/<int:id>/', it.AssetDetailView.as_view(), name='asset_detail'),
    path('it/system-status/', it.SystemStatusListView.as_view(), name='system_status'),
    path('tickets/', it.TicketListCreateView.as_view(), name='ticket_list'),
    path('tickets/<int:id>/', it.TicketDetailView.as_view(), name='ticket_detail'),
    # inventory
    path('inventory/products/', inventory.InventoryProductsView.as_view(), name='inventory_products'),
    path(
        'inventory/products/<int:id>/', inventory.InventoryProductDetailView.as_view(), name='inventory_product_detail'
    ),
    path('inventory/dashboard/', inventory.InventoryDashboardView.as_view(), name='inventory_dashboard_kpis'),
    path('inventory/flow/', inventory.InventoryFlowView.as_view(), name='inventory_flow'),
    path('inventory/suppliers/', inventory.SupplierListView.as_view(), name='supplier_list'),
    path('inventory/stock-movements/', inventory.StockMovementCreateView.as_view(), name='stock_movements'),
    # sales
    path('sales/dashboard/', sales.SalesDashboardView.as_view(), name='sales_dashboard_kpis'),
    path('sales/daily-orders/', sales.SalesDailyOrdersView.as_view(), name='sales_daily_orders'),
    path('sales/top-products/', sales.SalesTopProductsView.as_view(), name='sales_top_products'),
    path('sales/channel-split/', sales.SalesChannelSplitView.as_view(), name='sales_channel_split'),
    path('sales/revenue-trend/', sales.SalesRevenueTrendView.as_view(), name='sales_revenue_trend'),
    path('products/', sales.SalesProductsView.as_view(), name='product_catalogue'),
    path('customers/', sales.CustomerListView.as_view(), name='customer_list'),
    path('customers/<int:id>/', sales.CustomerDetailView.as_view(), name='customer_detail'),
    path('invoices/', sales.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/<int:id>/', sales.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('orders/', sales.OrderListView.as_view(), name='order_list'),
    path('orders/<int:id>/', sales.OrderDetailView.as_view(), name='order_detail'),
    # reports
    path('reports/', reports.ReportListView.as_view(), name='report_list'),
    path('reports/<int:id>/download/', reports.ReportDownloadView.as_view(), name='report_download'),
    path('reports/<int:id>/view/', reports.ReportViewView.as_view(), name='report_view'),
    path('reports/generate/<slug:slug>/', reports.ReportGenerateView.as_view(), name='report_generate'),
    # assistant
    path('assistant/chat/', assistant.AssistantChatView.as_view(), name='assistant_chat'),
    path('assistant/sessions/', assistant.ConversationSessionListCreateView.as_view(), name='assistant_sessions'),
    path(
        'assistant/sessions/<int:session_id>/',
        assistant.ConversationSessionDetailView.as_view(),
        name='assistant_session_detail',
    ),
    # workflows
    path('workflows/', workflows.WorkflowListView.as_view(), name='workflow_list'),
    path('workflows/triggers/', workflows.WorkflowTriggersView.as_view(), name='workflow_triggers'),
    path('workflows/actions/', workflows.WorkflowActionsView.as_view(), name='workflow_actions'),
    path('workflows/logs/', workflows.WorkflowLogListView.as_view(), name='workflow_logs'),
    path('workflows/<int:id>/', workflows.WorkflowDetailView.as_view(), name='workflow_detail'),
    path('workflows/<int:id>/toggle/', workflows.WorkflowToggleView.as_view(), name='workflow_toggle'),
    # notifications
    path('notifications/', notifications.NotificationListView.as_view(), name='notification_list'),
    path(
        'notifications/mark-all-read/',
        notifications.NotificationMarkAllReadView.as_view(),
        name='notification_mark_all_read',
    ),
    path('notifications/<int:id>/', notifications.NotificationDetailView.as_view(), name='notification_detail'),
    # legacy
    path('is_even/', legacy.is_even, name='is_even'),
]
