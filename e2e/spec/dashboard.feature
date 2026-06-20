# language: en
# BDD Spec — Dashboard CRUD (P0-D)

@dashboard
Feature: Dashboard CRUD
  As a business user
  I need to create, edit, organize and delete dashboards

  Scenario: List all dashboards
    When the client calls "/api/v1/dashboard"
    Then the result contains at least one dashboard

  Scenario: Get dashboard details
    Given there is a dashboard with id=N
    When the client calls "/api/v1/dashboard/{id}"
    Then the response contains the dashboard layout JSON

  Scenario: Create an empty dashboard
    When the user creates an empty dashboard titled "E2E Dashboard"
    Then the dashboard appears in the list

  Scenario: Edit a dashboard title
    Given a dashboard has been created
    When the user modifies its title
    Then the new title is persisted

  Scenario: Delete a dashboard
    Given a temporary dashboard has been created
    When the user deletes that dashboard
    Then the dashboard no longer appears in the list

  Scenario: Dashboard layout contains a chart placeholder
    Given a dashboard exists
    When the user adds a chart to the dashboard
    Then the layout JSON includes that chart

  Scenario: Export a dashboard to ZIP
    Given a dashboard with charts exists
    When the user exports the dashboard
    Then a ZIP file is downloaded

  Scenario: Import a dashboard from ZIP
    Given a dashboard export ZIP exists
    When the user uploads that file
    Then a new dashboard is created
