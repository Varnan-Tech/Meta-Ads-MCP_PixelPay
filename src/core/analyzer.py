"""
AI-powered campaign analysis engine for Meta Ads MCP server.
"""
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    # Try absolute imports first (when run as part of package)
    from ..tools.campaigns import get_campaigns
    from ..tools.insights import get_insights, calculate_roas, calculate_ctr, calculate_cpc, calculate_cpm
    from ..config.constants import ANALYSIS_THRESHOLDS
    from ..utils.logger import logger
except ImportError:
    # Fall back to relative imports (when run as script from src directory)
    import sys
    import os
    # Add current directory to path for relative imports
    sys.path.insert(0, os.path.dirname(__file__))
    from tools.campaigns import get_campaigns
    from tools.insights import get_insights, calculate_roas, calculate_ctr, calculate_cpc, calculate_cpm
    from config.constants import ANALYSIS_THRESHOLDS
    from utils.logger import logger


@dataclass
class CampaignAnalysis:
    """Analysis results for a single campaign."""
    campaign_id: str
    campaign_name: str
    spend: float
    impressions: int
    clicks: int
    conversions: int
    conversion_value: float
    ctr: float
    cpc: float
    cpm: float
    roas: float
    status: str
    days_running: int
    performance_score: float
    issues: List[str]
    recommendations: List[str]


@dataclass
class AccountAnalysis:
    """Overall account analysis results."""
    total_spend: float
    total_conversions: int
    average_roas: float
    account_health: str
    top_performers: List[CampaignAnalysis]
    underperformers: List[CampaignAnalysis]
    recommendations: List[str]
    action_items: List[Dict[str, Any]]


class CampaignAnalyzer:
    """
    AI-powered campaign analysis engine.

    Analyzes campaign performance and provides actionable recommendations
    for optimization and budget allocation.
    """

    def __init__(self):
        self.thresholds = ANALYSIS_THRESHOLDS

    def analyze_account_campaigns(self, account_id: str, time_range: str = 'last_30d') -> Dict[str, Any]:
        """
        Analyze all campaigns in an account.

        Args:
            account_id: Meta ad account ID
            time_range: Time range for analysis

        Returns:
            Complete account analysis
        """
        try:
            # Get all active campaigns
            campaigns_response = get_campaigns(account_id, status='ACTIVE')

            if not campaigns_response.get('success'):
                return {
                    "success": False,
                    "error": f"Failed to get campaigns: {campaigns_response.get('error')}"
                }

            campaigns = campaigns_response.get('campaigns', [])

            if not campaigns:
                return {
                    "success": True,
                    "analysis": {
                        "message": "No active campaigns found to analyze",
                        "total_spend": 0,
                        "total_conversions": 0,
                        "average_roas": 0,
                        "account_health": "No Data"
                    }
                }

            # Analyze each campaign
            campaign_analyses = []
            total_spend = 0
            total_conversions = 0

            for campaign in campaigns:
                analysis = self._analyze_single_campaign(campaign, time_range)
                if analysis:
                    campaign_analyses.append(analysis)
                    total_spend += analysis.spend
                    total_conversions += analysis.conversions

            if not campaign_analyses:
                return {
                    "success": True,
                    "analysis": {
                        "message": "No campaign data available for analysis",
                        "total_spend": 0,
                        "total_conversions": 0,
                        "average_roas": 0,
                        "account_health": "No Data"
                    }
                }

            # Calculate overall metrics
            average_roas = sum(c.roas for c in campaign_analyses) / len(campaign_analyses) if campaign_analyses else 0

            # Identify top and under performers
            top_performers = sorted(campaign_analyses, key=lambda x: x.performance_score, reverse=True)[:3]
            underperformers = sorted(campaign_analyses, key=lambda x: x.performance_score)[:3]

            # Generate recommendations
            recommendations = self._generate_account_recommendations(campaign_analyses)

            # Generate action items
            action_items = self._generate_action_items(campaign_analyses)

            # Determine account health
            account_health = self._determine_account_health(average_roas, campaign_analyses)

            account_analysis = AccountAnalysis(
                total_spend=total_spend,
                total_conversions=total_conversions,
                average_roas=average_roas,
                account_health=account_health,
                top_performers=top_performers,
                underperformers=underperformers,
                recommendations=recommendations,
                action_items=action_items
            )

            return {
                "success": True,
                "analysis": self._format_account_analysis(account_analysis)
            }

        except Exception as e:
            logger.error(f"Error in analyze_account_campaigns for {account_id}: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }

    def _analyze_single_campaign(self, campaign: Dict[str, Any], time_range: str) -> Optional[CampaignAnalysis]:
        """
        Analyze a single campaign's performance.

        Args:
            campaign: Campaign data
            time_range: Time range for analysis

        Returns:
            CampaignAnalysis object or None if analysis failed
        """
        try:
            campaign_id = campaign.get('id')
            if not campaign_id:
                return None

            # Get campaign insights
            insights_response = get_insights(campaign_id, time_range)

            if not insights_response.get('success'):
                logger.warning(f"Failed to get insights for campaign {campaign_id}")
                return None

            insights = insights_response.get('insights', {})

            # Extract metrics (use most recent data if multiple dates)
            latest_date = max(insights.keys()) if insights else None
            if not latest_date or latest_date not in insights:
                return None

            data = insights[latest_date]

            # Parse metrics
            spend = float(data.get('spend', 0) or 0)
            impressions = int(data.get('impressions', 0) or 0)
            clicks = int(data.get('clicks', 0) or 0)
            conversions = int(data.get('conversions', 0) or 0)
            conversion_value = float(data.get('conversion_value', 0) or 0)

            # Calculate derived metrics
            ctr = calculate_ctr(clicks, impressions)
            cpc = calculate_cpc(spend, clicks)
            cpm = calculate_cpm(spend, impressions)
            roas = calculate_roas(spend, conversion_value)

            # Calculate days running (rough estimate)
            created_date = campaign.get('created_time', '')
            days_running = 30  # Default for time_range='last_30d'
            if created_date:
                try:
                    from datetime import datetime
                    created = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                    days_running = min((datetime.now() - created.replace(tzinfo=None)).days, 30)
                except:
                    pass

            # Calculate performance score (0-100)
            performance_score = self._calculate_performance_score(spend, roas, ctr, conversions)

            # Identify issues and recommendations
            issues = self._identify_campaign_issues(spend, roas, ctr, cpc, conversions, days_running)
            recommendations = self._generate_campaign_recommendations(spend, roas, ctr, cpc, conversions, issues)

            return CampaignAnalysis(
                campaign_id=campaign_id,
                campaign_name=campaign.get('name', 'Unknown'),
                spend=spend,
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                conversion_value=conversion_value,
                ctr=ctr,
                cpc=cpc,
                cpm=cpm,
                roas=roas,
                status=campaign.get('status', 'UNKNOWN'),
                days_running=days_running,
                performance_score=performance_score,
                issues=issues,
                recommendations=recommendations
            )

        except Exception as e:
            logger.error(f"Error analyzing campaign {campaign.get('id')}: {e}")
            return None

    def _calculate_performance_score(self, spend: float, roas: float, ctr: float,
                                   conversions: int) -> float:
        """
        Calculate overall performance score for a campaign (0-100).

        Args:
            spend: Amount spent
            roas: Return on ad spend
            ctr: Click-through rate
            conversions: Number of conversions

        Returns:
            Performance score
        """
        score = 50  # Base score

        # ROAS scoring (40% weight)
        if roas >= self.thresholds['good_roas']:
            score += 40
        elif roas >= 2.0:
            score += 25
        elif roas >= 1.0:
            score += 10
        elif roas > 0:
            score += 5

        # CTR scoring (30% weight)
        if ctr >= self.thresholds['good_ctr'] / 100:  # Convert percentage to decimal
            score += 30
        elif ctr >= 1.0 / 100:  # 1%
            score += 20
        elif ctr >= 0.5 / 100:  # 0.5%
            score += 10

        # Conversions scoring (20% weight)
        if conversions >= 50:
            score += 20
        elif conversions >= 20:
            score += 15
        elif conversions >= 10:
            score += 10
        elif conversions >= 5:
            score += 5

        # Spend efficiency (10% weight)
        if spend > 0 and conversions > 0:
            cost_per_conversion = spend / conversions
            if cost_per_conversion <= 20:  # Good efficiency
                score += 10
            elif cost_per_conversion <= 50:
                score += 5

        return min(score, 100)  # Cap at 100

    def _identify_campaign_issues(self, spend: float, roas: float, ctr: float,
                                cpc: float, conversions: int, days_running: int) -> List[str]:
        """
        Identify issues with a campaign.

        Args:
            spend: Amount spent
            roas: Return on ad spend
            ctr: Click-through rate
            cpc: Cost per click
            conversions: Number of conversions
            days_running: Days campaign has been running

        Returns:
            List of identified issues
        """
        issues = []

        if roas < 1.0 and spend > 50:
            issues.append("Negative ROI - spending more than earning")

        if ctr < 0.5 / 100 and spend > 25:  # Less than 0.5%
            issues.append("Very low click-through rate")

        if cpc > self.thresholds['high_cpc'] and spend > 100:
            issues.append("High cost per click")

        if conversions < self.thresholds['low_conversions'] and days_running > 7:
            issues.append("Low conversion volume")

        if spend == 0:
            issues.append("No spend detected - campaign may not be delivering")

        return issues

    def _generate_campaign_recommendations(self, spend: float, roas: float, ctr: float,
                                         cpc: float, conversions: int, issues: List[str]) -> List[str]:
        """
        Generate recommendations for a campaign.

        Args:
            spend: Amount spent
            roas: Return on ad spend
            ctr: Click-through rate
            cpc: Cost per click
            conversions: Number of conversions
            issues: List of identified issues

        Returns:
            List of recommendations
        """
        recommendations = []

        if "Negative ROI" in issues:
            recommendations.append("Consider pausing campaign - negative return on investment")
            recommendations.append("Review targeting and creative to improve performance")

        if "Very low click-through rate" in issues:
            recommendations.append("Test different ad creative or copy")
            recommendations.append("Review audience targeting for relevance")

        if "High cost per click" in issues:
            recommendations.append("Consider bid strategy adjustments")
            recommendations.append("Review audience size and competition")

        if "Low conversion volume" in issues:
            recommendations.append("Review landing page experience")
            recommendations.append("Test different call-to-action buttons")

        if not recommendations and roas > self.thresholds['good_roas']:
            recommendations.append("Campaign performing well - consider increasing budget")

        if not recommendations and ctr > self.thresholds['good_ctr'] / 100:
            recommendations.append("Good engagement - test audience expansion")

        return recommendations

    def _generate_account_recommendations(self, analyses: List[CampaignAnalysis]) -> List[str]:
        """
        Generate account-level recommendations.

        Args:
            analyses: List of campaign analyses

        Returns:
            List of account-level recommendations
        """
        recommendations = []

        # Find campaigns with negative ROI
        negative_roi = [a for a in analyses if a.roas < 1.0 and a.spend > 50]
        if negative_roi:
            recommendations.append(f"Pause {len(negative_roi)} underperforming campaigns with negative ROI")

        # Find top performers for budget increase
        top_performers = sorted(analyses, key=lambda x: x.roas, reverse=True)[:2]
        if top_performers and top_performers[0].roas > self.thresholds['good_roas']:
            recommendations.append(f"Increase budget for top performer: {top_performers[0].campaign_name}")

        # Check for campaigns with very low CTR
        low_ctr = [a for a in analyses if a.ctr < 0.5 / 100 and a.spend > 25]
        if low_ctr:
            recommendations.append(f"Review creative for {len(low_ctr)} campaigns with very low CTR")

        if not recommendations:
            recommendations.append("Account performing well - consider testing new campaigns")

        return recommendations

    def _generate_action_items(self, analyses: List[CampaignAnalysis]) -> List[Dict[str, Any]]:
        """
        Generate prioritized action items.

        Args:
            analyses: List of campaign analyses

        Returns:
            List of action items with priority
        """
        action_items = []

        # High priority: Pause negative ROI campaigns
        for analysis in analyses:
            if analysis.roas < 1.0 and analysis.spend > 100:
                action_items.append({
                    "priority": "high",
                    "action": "pause_campaign",
                    "campaign_id": analysis.campaign_id,
                    "campaign_name": analysis.campaign_name,
                    "reason": f"Negative ROI ({analysis.roas:.2f}x) after significant spend (${analysis.spend:.2f})"
                })

        # Medium priority: Review low CTR campaigns
        for analysis in analyses:
            if analysis.ctr < 0.5 / 100 and analysis.spend > 50:
                action_items.append({
                    "priority": "medium",
                    "action": "review_creative",
                    "campaign_id": analysis.campaign_id,
                    "campaign_name": analysis.campaign_name,
                    "reason": f"Very low CTR ({analysis.ctr*100:.2f}%) despite spend"
                })

        # Low priority: Scale successful campaigns
        for analysis in analyses:
            if analysis.roas > self.thresholds['good_roas'] and analysis.performance_score > 80:
                action_items.append({
                    "priority": "low",
                    "action": "increase_budget",
                    "campaign_id": analysis.campaign_id,
                    "campaign_name": analysis.campaign_name,
                    "reason": f"High-performing campaign (ROAS: {analysis.roas:.2f}x, Score: {analysis.performance_score:.0f})"
                })

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        action_items.sort(key=lambda x: priority_order.get(x["priority"], 2))

        return action_items

    def _determine_account_health(self, average_roas: float, analyses: List[CampaignAnalysis]) -> str:
        """
        Determine overall account health.

        Args:
            average_roas: Average ROAS across all campaigns
            analyses: List of campaign analyses

        Returns:
            Account health status
        """
        if average_roas >= self.thresholds['good_roas']:
            return "Excellent"
        elif average_roas >= 2.0:
            return "Good"
        elif average_roas >= 1.0:
            return "Fair"
        else:
            return "Needs Attention"

    def _format_account_analysis(self, analysis: AccountAnalysis) -> Dict[str, Any]:
        """
        Format account analysis for response.

        Args:
            analysis: AccountAnalysis object

        Returns:
            Formatted analysis dictionary
        """
        return {
            "summary": {
                "total_spend": f"${analysis.total_spend:.2f}",
                "total_conversions": analysis.total_conversions,
                "average_roas": f"{analysis.average_roas:.2f}x",
                "account_health": analysis.account_health
            },
            "top_performers": [
                {
                    "campaign_id": p.campaign_id,
                    "campaign_name": p.campaign_name,
                    "roas": f"{p.roas:.2f}x",
                    "spend": f"${p.spend:.2f}",
                    "conversions": p.conversions,
                    "performance_score": f"{p.performance_score:.0f}/100",
                    "reason": "High ROAS and consistent performance"
                }
                for p in analysis.top_performers
            ],
            "underperformers": [
                {
                    "campaign_id": u.campaign_id,
                    "campaign_name": u.campaign_name,
                    "roas": f"{u.roas:.2f}x",
                    "spend": f"${u.spend:.2f}",
                    "conversions": u.conversions,
                    "issues": u.issues,
                    "recommendation": "Consider pausing or adjusting targeting"
                }
                for u in analysis.underperformers
            ],
            "recommendations": analysis.recommendations,
            "action_items": analysis.action_items
        }


# Global analyzer instance
campaign_analyzer = CampaignAnalyzer()


def analyze_campaigns(account_id: str, time_range: str = 'last_30d', focus: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze campaigns for an account (main entry point).

    Args:
        account_id: Meta ad account ID
        time_range: Time range for analysis
        focus: Analysis focus area (optional)

    Returns:
        Analysis results
    """
    return campaign_analyzer.analyze_account_campaigns(account_id, time_range)


