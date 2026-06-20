# language: en
# BDD Spec — Embed & public API (P3-B)

@embed
Feature: Embedded dashboards and public API
  As a developer
  I need embeddable dashboards and access to the public REST API

  Scenario: Create an embed credential
    Given a dashboard exists
    When the user creates an embed configuration
    Then an embed uuid is returned

  Scenario: Get a public embed URL
    Given an embed uuid exists
    When the embed URL is requested
    Then an accessible URL is returned

  Scenario: Embed page renders
    Given an embed uuid exists
    When the embed page is opened
    Then the dashboard is displayed

@api
Feature: Public REST API
  As a developer
  I need the REST API to be discoverable and protected by CSRF

  Scenario: API endpoint list
    When the client calls "/api/v1/"
    Then all available API resources are listed

  Scenario: CSRF is required for write operations
    When the client sends a POST without a CSRF token
    Then the response is 401 or 403
