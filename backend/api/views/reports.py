"""Reports: listing, generation, viewing and download, scoped by category to the user's role."""

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    Report,
    User,
)
from ..serializers.reports import ReportSerializer

# Which roles may read reports of a given category. CEO always sees everything;
# reports with a blank/unknown category are CEO-only.
REPORT_CATEGORY_ROLES = {
    Report.Category.SALES: {User.Role.CEO, User.Role.SALES},
    Report.Category.FINANCE: {User.Role.CEO},
    Report.Category.INVENTORY: {User.Role.CEO, User.Role.INVENTORY},
    Report.Category.HR: {User.Role.CEO, User.Role.HR},
    Report.Category.IT: {User.Role.CEO, User.Role.IT},
}


def _allowed_report_categories(user):
    """Return the set of report categories the user is permitted to read."""
    if user.role == User.Role.CEO:
        return set(Report.Category.values)
    return {category for category, roles in REPORT_CATEGORY_ROLES.items() if user.role in roles}


def _can_access_report(user, report):
    if user.role == User.Role.CEO:
        return True
    return user.role in REPORT_CATEGORY_ROLES.get(report.category, set())


class ReportListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        allowed_categories = _allowed_report_categories(request.user)
        reports = Report.objects.filter(category__in=allowed_categories).order_by('-generated_at')
        category = request.query_params.get('category')
        if category:
            if category not in allowed_categories:
                return Response(
                    {'detail': 'You do not have access to reports in this category.'}, status=status.HTTP_403_FORBIDDEN
                )
            reports = reports.filter(category=category)
        return Response(ReportSerializer(reports, many=True).data)


class ReportDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        from pathlib import Path

        report = get_object_or_404(Report, id=id)
        if not _can_access_report(request.user, report):
            return Response({'detail': 'You do not have access to this report.'}, status=status.HTTP_403_FORBIDDEN)
        if not report.file_path:
            return Response({'detail': 'File not available.'}, status=status.HTTP_404_NOT_FOUND)
        path = Path(report.file_path)
        if not path.exists():
            return Response({'detail': 'File not found on server.'}, status=status.HTTP_404_NOT_FOUND)

        # Determine content type based on file extension
        ext = path.suffix.lower()
        if ext == '.pdf':
            content_type = 'application/pdf'
        elif ext == '.csv':
            content_type = 'text/csv'
        else:
            content_type = 'application/octet-stream'

        return FileResponse(open(path, 'rb'), content_type=content_type, as_attachment=True, filename=path.name)


class ReportGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        from ..agent import AgentRunner, get_registry

        if request.user.role != User.Role.CEO and not request.user.is_staff:
            raise PermissionDenied('Only CEO or admin can generate reports.')
        report = get_object_or_404(Report, slug=slug)
        directives = (request.data.get('directives') or '').strip()

        directives_line = f' Additional focus: {directives}.' if directives else ''
        message = (
            f'Generate the {report.name} report (slug: "{report.slug}", category: {report.category}, period: {report.period}).'
            f' Step 1: use the available query tools to gather all relevant real data from the app for this report category.'
            f' Step 2: call generate_report with slug="{report.slug}" and pass the collected data serialised as a JSON string in context_data.'
            f'{directives_line}'
        )

        agent = AgentRunner(user=request.user, current_page='/reports')
        agent.register_tools(get_registry().get_all())
        result = agent.run(message=message, history=[])

        report.refresh_from_db()
        return Response(
            {
                'response': result.get('response')
                or f'The {report.name} report has been generated and is ready to view.',
                'report': ReportSerializer(report).data,
            },
            status=status.HTTP_200_OK,
        )


class ReportViewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        from pathlib import Path

        report = get_object_or_404(Report, id=id)
        if not _can_access_report(request.user, report):
            return Response({'detail': 'You do not have access to this report.'}, status=status.HTTP_403_FORBIDDEN)
        if not report.file_path:
            return Response({'detail': 'Report not generated yet.'}, status=status.HTTP_404_NOT_FOUND)
        path = Path(report.file_path)
        if not path.exists():
            return Response({'detail': 'File not found on server.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'html': path.read_text(encoding='utf-8'), 'filename': path.name})
