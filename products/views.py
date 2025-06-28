import datetime
import openpyxl
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from products.models import ProductionOrder, InventoryItem


def user_is_allowed(user):
    val = False
    for i in user.groups.all():
        if i.name in ["سرپرست مونتاژ", "کارمند IT", "سرپرست IT", "سرپرست حسابداری صنعتی"] or user.access_level in [0, -1]:
            val = True
            break

    return val

@login_required
@require_GET
@user_passes_test(user_is_allowed)
def projects_products_list(request):
    products = InventoryItem.objects.all().order_by("project__name", "product__name", "-quantity")

    match request.GET.get("export"):
        # case "pdf":
        #     return export_monthly_pdf(request, performance_data)
        case "excel":
            return export_excel_projects_prodects_list(request, products)
    #  gunicorn fccc_targets.wsgi:application --bind 127.0.0.1:8001
    context = {
        "products": products
    }
    return render(request, "products/projects_list.html", context)



def export_excel_projects_prodects_list(request, products):
    data_excel = products
    d = datetime.datetime.now()
    year = d.year
    month = d.month

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "محصولات تولید شده"
    ws.append(["#", "نام پروژه", "نام محصول", "نام کاربر", "تعداد تولید شده"])

    for i, item in enumerate(data_excel, 1):
        ws.append([i, item.project.name, item.product.name,
                   item.user.get_full_name(), item.quantity])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=monthly_performance_{year}_{month}.xlsx'
    wb.save(response)
    return response

