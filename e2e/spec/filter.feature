# language: en
# BDD Spec — Dashboard filters (P1-A)

@dashboard @filter
Feature: Dashboard filters
  As a business user
  I need native filters, cross-filters, time ranges, URL params and auto-refresh

  Scenario: Create a native filter
    Given a dashboard with charts exists
    When the user adds a native filter in edit mode
    Then the filter is visible on the dashboard

  Scenario: Delete a native filter
    Given the dashboard has a filter
    When the user deletes that filter
    Then the filter is no longer visible

  Scenario: Changing a filter value refreshes the chart
    Given the dashboard has a filter
    When the user changes the filter value
    Then the related chart is refreshed

  Scenario: Time range filter
    Given the dashboard has a time filter
    When the user selects a time range
    Then the chart shows the selected time range

  Scenario: Numeric range filter
    Given the dashboard has a numeric filter
    When the user enters a numeric range
    Then the chart is filtered by that range

  Scenario: Single-value select filter
    Given the dashboard has a select filter
    When the user selects a value
    Then the chart is filtered to that value

  Scenario: Multi-value select filter
    Given the dashboard has a multi-select filter
    When the user selects multiple values
    Then the chart shows all matching items

  Scenario: Cross-filter between charts
    Given the dashboard has multiple charts
    When the user clicks a dimension on chart A
    Then chart B is filtered automatically

  Scenario: URL parameter passthrough
    Given the dashboard supports URL parameters
    When the user opens "?param=value"
    Then the dashboard is filtered by the parameter

  Scenario: Auto refresh
    Given the dashboard has auto-refresh enabled
    When the refresh interval elapses
    Then the dashboard reloads automatically
