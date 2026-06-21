# language: en
# BDD Spec — Chart data & explore JSON (P4-G)

@chart_data
Feature: Chart data and explore endpoints
  As a chart consumer
  I need direct access to the chart data and explore form data

  Scenario: Chart data query returns rows
    Given a dataset exists
    When the user posts a query to "/api/v1/chart/data"
    Then the response contains rows

  Scenario: Chart data query with aggregation
    Given a dataset exists
    When the user posts a query with a groupby + metric
    Then the response contains aggregated rows

  Scenario: Explore endpoint returns a form data skeleton
    When the client calls "/api/v1/explore/?q=..."
    Then the response is a valid explore config object

  Scenario: Explore endpoint returns dataset for a slice
    Given a chart exists
    When the user calls "/api/v1/explore/?slice_id={id}"
    Then the response contains the dataset and form data

  Scenario: Chart favorite status returns favorited flag
    Given a chart exists
    When the user calls "/api/v1/chart/favorite_status/?q=[id_list]"
    Then the response contains a list with the favorite flag

@sqllab_state
Feature: SQL Lab state
  As a SQL Lab user
  I need to retrieve the active tab and tab state

  Scenario: SQL Lab tab state
    When the client calls "/api/v1/sqllab/"
    Then the response contains the active tab and tab_state_ids
