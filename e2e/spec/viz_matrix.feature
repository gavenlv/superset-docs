# language: en
# BDD Spec — Viz type matrix (P0-E)
# 34 viz_types covered, one Scenario Outline per type.

@chart @viz
Feature: Viz type rendering matrix
  As an analyst
  I need every Superset viz_type to be able to render against example data

  Scenario Outline: Render viz_type "<viz>" against dataset "<dataset>"
    Given the dataset "<dataset>" is available
    When the user creates a chart with viz_type="<viz>"
    Then the chart renders without errors
    And the chart shows a result payload from "/api/v1/chart/{id}/data"

    Examples:
      | viz                  | dataset            |
      | table                | birth_names        |
      | pivot_table          | birth_names        |
      | pivot_table_v2       | birth_names        |
      | big_number           | birth_names        |
      | big_number_total     | birth_names        |
      | big_number_period_compare | birth_names   |
      | percent_change       | birth_names        |
      | gauge                | birth_names        |
      | line                 | birth_names        |
      | timeseries           | birth_names        |
      | bar                  | birth_names        |
      | timeseries_bar       | birth_names        |
      | area                 | birth_names        |
      | compare              | birth_names        |
      | step                 | birth_names        |
      | candlestick          | birth_names        |
      | pie                  | birth_names        |
      | donut                | birth_names        |
      | treemap              | birth_names        |
      | sunburst             | birth_names        |
      | funnel               | video_game_sales   |
      | sankey               | video_game_sales   |
      | icicle               | birth_names        |
      | histogram            | birth_names        |
      | dist_bar             | birth_names        |
      | box_plot             | birth_names        |
      | violin               | birth_names        |
      | scatter              | birth_names        |
      | bubble               | birth_names        |
      | heatmap              | flights            |
      | correlation          | flights            |
      | calendar_heatmap     | flights            |
      | word_cloud           | birth_names        |
      | radar                | birth_names        |
