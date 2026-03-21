from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET

# Create your views here.
@require_GET
def is_even(request):
  try:
    number = int(request.GET.get('number'))
    result = (number % 2 == 0)
    return JsonResponse({'even': result})
  except (TypeError, ValueError):
    return JsonResponse({'error': 'Invalid or missing number parameter'}, status=400)