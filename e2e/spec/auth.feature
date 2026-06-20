# language: en
# BDD Spec — Health & Authentication
# Each Scenario maps 1:1 to a row in COVERAGE.md (P0 / Auth).
# Tags: @auth
# Version: [*] both 4.1 & 6.0, [@v4.1] only 4.1, [@v6.0] only 6.0

@auth
Feature: System health and authentication
  As a user of Superset
  I need the service to be reachable and to be able to log in / out securely

  Scenario: Health endpoint is reachable
    When the user requests the "/health" endpoint
    Then the response status is 200
    And the response body contains "OK"

  Scenario: Login page renders
    When the user opens the login page
    Then a username input is visible
    And a password input is visible
    And a submit button is visible

  Scenario: Admin logs in successfully
    Given the user is on the login page
    When the user enters username "admin" and password "admin"
    And the user clicks the submit button
    Then the browser navigates away from "/login/"
    And the current user is shown as "admin"

  Scenario: Wrong password is rejected
    Given the user is on the login page
    When the user enters username "admin" and password "wrong"
    And the user clicks the submit button
    Then the user remains on the login page
    And an error message is displayed

  Scenario: API login returns a JWT
    When the client calls "/api/v1/security/login" with valid credentials
    Then the response contains "access_token"

  Scenario: API logout invalidates the session
    Given the user is logged in
    When the client calls "/api/v1/security/logout"
    Then the response status is 200

  Scenario: User logs out via UI
    Given the user is logged in
    When the user clicks the logout action
    Then the browser navigates to the login page
