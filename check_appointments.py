import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://vtdmv.cxmflow.com/Appointment/Index/57479cc4-a999-4eee-a392-0a7a474a17aa"
DAYS_TO_CHECK = 4  # Check for appointments in the next 4 days

def setup_driver():
    """Sets up the Chrome webdriver."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in headless mode (no GUI)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def click_element(driver, by, value, timeout=20):
    """Waits for an element to be clickable and then clicks it."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
        element.click()
        time.sleep(1) # Allow time for page to load after click
    except TimeoutException:
        print(f"Error: Element with {by}='{value}' not found or clickable within {timeout} seconds.")
        raise
    except Exception as e:
        print(f"Error clicking element {by}='{value}': {e}")
        raise

def navigate_to_services(driver):
    """Navigates through the initial appointment scheduling steps."""
    print("Navigating to services...")
    driver.get(BASE_URL)

    # Click "Schedule an Appointment" button - this is actually a div
    # The text "Schedule an Appointment" is in a nested div with class "serviceprofilelabel"
    # The clickable parent div has class "serviceprofilebutton"
    click_element(driver, By.XPATH, "//div[contains(@class, 'serviceprofilelabel') and normalize-space(text())='Schedule an Appointment']/ancestor::div[contains(@class,'serviceprofilebutton')][1]")
    print("Clicked 'Schedule an Appointment' (div)")
    time.sleep(1.5) # Allow time for JS to trigger next action and page to load. Increased slightly.

    # Click "Registration/Title" service category
    # The clickable element has classes "QflowObjectItem" and "displaydata-text", and a "data-id" attribute.
    click_element(driver, By.XPATH, "//div[contains(@class, 'QflowObjectItem') and contains(@class, 'displaydata-text') and @data-id='Registration/Title']")
    print("Clicked 'Registration/Title'")
    time.sleep(1.5) # Allow time for JS to trigger next action and page to load


    # Click "Registrations (New, Transfer, Out of State)" service
    # The data-id for this is "34-"
    click_element(driver, By.XPATH, "//div[contains(@class, 'QflowObjectItem') and contains(@class, 'displaydata-text') and @data-id='34-']")
    print("Clicked 'Registrations (New, Transfer, Out of State)' (data-id='34-')")
    time.sleep(1.5) # Allow time for JS to trigger next action and page to load

    print("Navigation to office selection complete.")

def get_available_locations(driver):
    """Gets a list of available DMV locations and their data-ids."""
    print("Fetching available locations...")
    locations_data = []
    try:
        # Locations are divs with class "QflowObjectItem displaydata-text" and a "data-id"
        # The name is in a child div with class "center-textDiv"
        location_elements_outers = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'QflowObjectItem') and contains(@class, 'displaydata-text') and @data-id]"))
        )
        if not location_elements_outers:
            print("No location elements found. The page structure might have changed.")
            return []

        for outer_div in location_elements_outers:
            data_id = outer_div.get_attribute("data-id")
            try:
                name_div = outer_div.find_element(By.XPATH, ".//div[contains(@class, 'center-textDiv')]")
                full_text = name_div.text.strip()
                # Location name is usually the first line before the address details
                location_name = full_text.split('\n')[0].strip()
                if location_name and data_id:
                    locations_data.append({"name": location_name, "data_id": data_id})
            except NoSuchElementException:
                print(f"Could not find name_div for an element with data-id {data_id}")
            except Exception as e_inner:
                print(f"Error processing a location element: {e_inner}")

        if not locations_data:
            print("No locations with names and data-ids found.")
            return []

        print(f"Found locations: {locations_data}")
        return locations_data
    except TimeoutException:
        print("Error: Could not find location elements on the page.")
        return []
    except Exception as e:
        print(f"Error fetching locations: {e}")
        return []

def check_location_appointments(driver, location_info):
    """Checks a specific location for appointments within the next DAYS_TO_CHECK."""
    location_name = location_info["name"]
    location_data_id = location_info["data_id"]
    print(f"Checking appointments for: {location_name} (data-id: {location_data_id})")
    found_appointments = []

    try:
        # Click on the location using its data-id
        click_element(driver, By.XPATH, f"//div[contains(@class, 'QflowObjectItem') and contains(@class, 'displaydata-text') and @data-id='{location_data_id}']")
        print(f"Clicked location: {location_name}")
        time.sleep(1.5) # Allow time for calendar page to load
    except Exception as e:
        print(f"Could not click on location {location_name} (data-id: {location_data_id}). It might be unavailable or there's a page load issue: {e}")
        # Attempt to go back to location selection if possible (though the new back button is more reliable)
        try:
            click_element(driver, By.ID, "BackButton")
            print("Clicked 'Back' button (ID: BackButton) after failing to click location.")
            time.sleep(1)
        except Exception as e_back:
            print(f"Could not find or click 'Back' button (ID: BackButton) after failing to click location: {e_back}")
        return found_appointments # Skip this location

    # Simplified check: Look for the "Next Available" div with id "SingleDateTime"
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "SingleDateTime")))
        single_date_time_div = driver.find_element(By.ID, "SingleDateTime")

        data_datetime_str = single_date_time_div.get_attribute("data-datetime") # e.g., "7/18/2025 12:25:00 PM"
        visible_text = single_date_time_div.text.strip() # e.g., "18 July 2025 at 12:25 PM"

        print(f"Found 'Next Available' div: {visible_text} (data: {data_datetime_str})")

        if data_datetime_str:
            # Try parsing with AM/PM first
            try:
                appointment_dt = datetime.strptime(data_datetime_str, "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                # Fallback if AM/PM is missing or format is slightly different (e.g. 24-hour time)
                try:
                    appointment_dt = datetime.strptime(data_datetime_str, "%m/%d/%Y %H:%M:%S")
                except ValueError as ve_fallback:
                    print(f"Could not parse data-datetime string '{data_datetime_str}': {ve_fallback}")
                    appointment_dt = None

            if appointment_dt:
                now = datetime.now()
                # Check if the appointment is today or within the next DAYS_TO_CHECK days
                # And also ensure it's not in the past (though 'Next Available' shouldn't be)
                if now.date() <= appointment_dt.date() <= (now + timedelta(days=DAYS_TO_CHECK)).date():
                    # Check if it's a weekday (Monday=0, Sunday=6)
                    if appointment_dt.weekday() < 5:
                        appointment_info = f"APPOINTMENT FOUND: {location_name} on {appointment_dt.strftime('%A, %B %d, %Y at %I:%M %p')}"
                        print(appointment_info)
                        found_appointments.append(appointment_info)
                    else:
                        print(f"Next available slot at {location_name} ({appointment_dt.strftime('%A, %B %d')}) is a weekend. Skipping.")
                else:
                    print(f"Next available slot at {location_name} ({appointment_dt.strftime('%A, %B %d')}) is outside the desired {DAYS_TO_CHECK}-day window.")
        else:
            print(f"No 'data-datetime' attribute found in SingleDateTime div for {location_name}.")

    except TimeoutException:
        print(f"No 'Next Available' (SingleDateTime div) found for {location_name} within 10 seconds. Checking calendar as fallback.")
        # --- Fallback to detailed calendar check if SingleDateTime is not found ---
        # This part is removed as per user request to only check SingleDateTime
        print("Fallback calendar check is currently disabled as per user request.")
        pass # If SingleDateTime not found, we assume no quick appointment.

    except NoSuchElementException:
        print(f"No 'Next Available' (SingleDateTime div) found for {location_name}. Assuming no quick appointment.")
    except Exception as e:
        print(f"Error checking SingleDateTime div for {location_name}: {e}")

    # After checking, navigate back to the office selection page
    try:
        print(f"Trying to go back to office selection from {location_name}'s date/time page.")
        # The "Office" page HTML shows a back button with id="BackButton"
        click_element(driver, By.ID, "BackButton")
        print("Clicked 'Back' button (ID: BackButton).")
        time.sleep(1.5) # Allow time to return to office list
    except Exception as e:
        print(f"Error trying to navigate back to office selection from {location_name} using BackButton ID: {e}")
        # As a more robust fallback if ID fails, try common back button texts/classes
        try:
            change_location_button = driver.find_elements(By.XPATH, "//button[contains(., 'Change Location')] | //button[contains(@class, 'p-button-link') and .//span[contains(text(), 'Back')]] | //button[contains(text(),'Back')]")
            if change_location_button:
                change_location_button[0].click()
                print("Clicked a fallback 'Back' or 'Change Location' button.")
                time.sleep(1.5)
            else:
                print("No obvious 'Back' or 'Change Location' button found. Re-navigation might be needed if loop continues.")
        except Exception as e_fallback_back:
            print(f"Error with fallback back button: {e_fallback_back}")
    return found_appointments

def main():
    driver = None
    all_found_appointments = []
    try:
        driver = setup_driver()

        # Initial navigation to get to the location selection page
        navigate_to_services(driver)

        # Get locations once
        locations = get_available_locations(driver)
        if not locations:
            print("No locations were found. Exiting.")
            return

        for i, location_name in enumerate(locations):
            print(f"\nProcessing location {i+1}/{len(locations)}: {location_name}")

            # If not on the location selection page (e.g., after checking a location's calendar),
            # we need to ensure we are back there or re-navigate.
            # A simple check: are location elements visible?
            # This check should be consistent with how get_available_locations finds elements.
            try:
                WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'QflowObjectItem') and contains(@class, 'displaydata-text') and @data-id]"))
                )
                print("Currently on location selection page (found QflowObjectItem with data-id).")
            except TimeoutException:
                print("Not on location selection page. Attempting to re-navigate to service selection...")
                # This means the 'back' navigation in check_location_appointments didn't work as expected.
                # Re-navigate to the service selection which should then show locations.
                # This is a recovery mechanism.
                try:
                    # Click "Registration/Title" service category
                    click_element(driver, By.XPATH, "//div[contains(@class, 'service-category-name') and contains(text(), 'Registration/Title')]")
                    print("Clicked 'Registration/Title' (recovery)")

                    # Click "Registrations (New, Transfer, Out of State)" service
                    click_element(driver, By.XPATH, "//div[contains(@class, 'service-name') and contains(text(), 'Registrations (New, Transfer, Out of State)')]")
                    print("Clicked 'Registrations (New, Transfer, Out of State)' (recovery)")

                    # Re-fetch locations in case page reloaded differently
                    current_locations_on_page = get_available_locations(driver)
                    if not any(loc == location_name for loc in current_locations_on_page):
                        print(f"Location {location_name} not found after re-navigation. Skipping.")
                        continue

                except Exception as e:
                    print(f"Failed to re-navigate to location selection: {e}. Skipping remaining locations.")
                    break # Exit the loop over locations as navigation is broken

            appointments = check_location_appointments(driver, location_name)
            all_found_appointments.extend(appointments)

            # After checking a location, ensure we are back on the location selection page for the next iteration.
            # The `check_location_appointments` function is responsible for returning to location list.
            # If it fails, the check at the start of this loop will attempt re-navigation.


        if not all_found_appointments:
            print("\nNo appointments found in any location for the specified dates.")
        else:
            print("\n--- Summary of Found Appointments ---")
            for appt in all_found_appointments:
                print(appt)

    except Exception as e:
        print(f"An unexpected error occurred in main: {e}")
    finally:
        if driver:
            print("Closing browser.")
            driver.quit()

if __name__ == "__main__":
    main()
