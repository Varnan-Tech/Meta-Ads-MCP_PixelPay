"""
Constants for Meta Ads MCP server.
"""
from typing import Dict, List


# Meta API Configuration
META_GRAPH_API_VERSION = "v22.0"
META_API_BASE_URL = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}"

# Campaign Objectives (ODAX - Outcome-Driven Ad Experience)
VALID_OBJECTIVES = {
    'OUTCOME_AWARENESS': 'Brand awareness and reach',
    'OUTCOME_TRAFFIC': 'Drive traffic to website/app',
    'OUTCOME_ENGAGEMENT': 'Post engagement, page likes, video views',
    'OUTCOME_LEADS': 'Lead generation',
    'OUTCOME_SALES': 'Conversions, purchases, catalog sales',
    'OUTCOME_APP_PROMOTION': 'App installs and engagement'
}

# Legacy objectives (NO LONGER VALID)
DEPRECATED_OBJECTIVES = [
    'BRAND_AWARENESS',  # Use OUTCOME_AWARENESS
    'LINK_CLICKS',      # Use OUTCOME_TRAFFIC
    'CONVERSIONS',      # Use OUTCOME_SALES
    'APP_INSTALLS',     # Use OUTCOME_APP_PROMOTION
]

# Campaign Status Values
CAMPAIGN_STATUSES = ['ACTIVE', 'PAUSED', 'DELETED', 'ARCHIVED']

# Essential Metrics for Insights
ESSENTIAL_METRICS = [
    'spend',           # Money spent
    'impressions',     # Times shown
    'reach',           # Unique people reached
    'clicks',          # Link clicks
    'ctr',             # Click-through rate
    'cpc',             # Cost per click
    'cpm',             # Cost per 1000 impressions
]

# Conversion Metrics
CONVERSION_METRICS = [
    'conversions',     # Conversion events
    'cost_per_conversion',
    'conversion_value',
    'roas',            # Return on ad spend
]

# Valid Breakdown Dimensions for Insights (from Meta API)
VALID_BREAKDOWNS = [
    'age',
    'gender',
    'country',
    'region',
    'placement',
    'publisher_platform',
    'platform_position',
    'device_platform',
    'product_id',
    'hourly_stats_aggregated_by_audience_time_zone',
    'hourly_stats_aggregated_by_advertiser_time_zone',
    'impression_device',
    'action_type',
    'action_target_id',
    'action_device',
    'action_carousel_card_id',
    'action_carousel_card_name',
    'action_destination',
    'action_reaction',
    'action_video_sound',
    'action_video_type',
    'frequency_value',
    'video_view_type',
    'video_view_length',
    'conversion_destination',
    'conversion_delay',
    'attribution_setting',
    'ad_extension_domain',
    'ad_extension_url',
    'ad_format_asset',
    'app_id',
    'body_asset',
    'breakdown_ad_objective',
    'breakdown_reporting_ad_id',
    'call_to_action_asset',
    'coarse_conversion_value',
    'comscore_market',
    'creative_automation_asset_id',
    'creative_relaxation_asset_type',
    'crm_advertiser_l12_territory_ids',
    'crm_advertiser_subvertical_id',
    'crm_advertiser_vertical_id',
    'crm_ult_advertiser_id',
    'description_asset',
    'fidelity_type',
    'flexible_format_asset_type',
    'gen_ai_asset_type',
    'hsid',
    'image_asset',
    'is_auto_advance',
    'is_conversion_id_modeled',
    'is_rendered_as_delayed_skip_ad',
    'landing_destination',
    'link_url_asset',
    'mdsa_landing_destination',
    'media_asset_url',
    'media_creator',
    'media_destination_url',
    'media_format',
    'media_origin_url',
    'media_text_content',
    'media_type',
    'postback_sequence_index',
    'product_brand_breakdown',
    'product_category_breakdown',
    'product_custom_label_0_breakdown',
    'product_custom_label_1_breakdown',
    'product_custom_label_2_breakdown',
    'product_custom_label_3_breakdown',
    'product_custom_label_4_breakdown',
    'product_group_content_id_breakdown',
    'product_group_id',
    'product_id',
    'product_set_id_breakdown',
    'redownload',
    'rta_ugc_topic',
    'skan_campaign_id',
    'skan_conversion_id',
    'skan_version',
    'sot_attribution_model_type',
    'sot_attribution_window',
    'sot_channel',
    'sot_event_type',
    'sot_source',
    'title_asset',
    'user_persona_id',
    'user_persona_name',
    'video_asset',
    'rule_set_id',
    'rule_set_name',
    'dma',
    'mmm',
    'place_page_id',
    'standard_event_content_type',
    'signal_source_bucket',
    'marketing_messages_btn_name',
    'impression_view_time_advertiser_hour_v2'
]

# Account-level only breakdowns (cannot be used with campaigns/ads)
ACCOUNT_ONLY_BREAKDOWNS = [
    'campaign',
    'adset'
]

# Engagement Metrics
ENGAGEMENT_METRICS = [
    'post_engagement',
    'post_reactions',
    'post_shares',
    'post_comments',
]

# Time Range Presets
TIME_RANGES = {
    'today': 'today',
    'yesterday': 'yesterday',
    'last_7d': 'last_7d',
    'last_14d': 'last_14d',
    'last_30d': 'last_30d',
    'this_month': 'this_month',
    'last_month': 'last_month',
    'lifetime': 'maximum'
}

# Analysis Thresholds
ANALYSIS_THRESHOLDS = {
    'good_roas': 3.0,        # Return on ad spend > 3x
    'good_ctr': 2.0,         # Click-through rate > 2%
    'high_cpc': 2.00,        # Cost per click > $2
    'low_conversions': 5,    # < 5 conversions
    'high_frequency': 5.0,   # Shown to same person > 5 times
}

# Validation Rules
VALIDATION_RULES = {
    'name': {
        'min_length': 1,
        'max_length': 400,
        'required': True
    },
    'objective': {
        'enum': list(VALID_OBJECTIVES.keys()),
        'required': True
    },
    'daily_budget': {
        'min': 100,  # $1.00 in cents
        'type': 'integer'
    },
    'lifetime_budget': {
        'min': 100,  # $1.00 in cents
        'type': 'integer'
    },
    'status': {
        'enum': CAMPAIGN_STATUSES,
        'default': 'PAUSED'
    }
}

# Status Transitions
VALID_TRANSITIONS = {
    'PAUSED': ['ACTIVE', 'DELETED'],
    'ACTIVE': ['PAUSED', 'DELETED'],
    'DELETED': [],  # Cannot un-delete
}

# Targeting Types
TARGETING_TYPES = {
    'interests': 'adinterest',
    'behaviors': 'adTargetingCategory',
    'demographics': 'demographics',
    'geo': 'adgeolocation'
}
