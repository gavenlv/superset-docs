# language: en
# BDD Spec — System settings (P3-C)

@misc
Feature: System settings
  As a user
  I need a personalized experience (logo, language, timezone, welcome page)

  Scenario: Welcome page
    When the user logs in
    Then the user is redirected to the welcome page
    And recent activity is visible

  Scenario: Logo configuration
    Given the admin has configured a custom logo
    When the user opens any page
    Then the custom logo is visible

  Scenario: Language switch
    Given the user switches the language to Chinese
    When the page is reloaded
    Then the UI is displayed in Chinese

  Scenario: Timezone display
    Given the user sets the timezone to "Asia/Shanghai"
    When the page displays times
    Then times use the Shanghai timezone
