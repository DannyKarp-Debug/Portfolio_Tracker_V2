"""
Dashboard route — unified portfolio overview.
"""

from flask import Blueprint, render_template
from app.services.portfolio_service import get_combined_dashboard

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Render the main dashboard page with combined portfolio data."""
    dashboard = get_combined_dashboard()
    return render_template("dashboard.html", dashboard=dashboard)
