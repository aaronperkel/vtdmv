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

    # Click "Schedule an Appointment" button
    click_element(driver, By.XPATH, "//button[contains(text(),'Schedule an Appointment')]")
    print("Clicked 'Schedule an Appointment'")

    # Click "Registration/Title" service category
    click_element(driver, By.XPATH, "//div[contains(@class, 'service-category-name') and contains(text(), 'Registration/Title')]")
    print("Clicked 'Registration/Title'")

    # Click "Registrations (New, Transfer, Out of State)" service
    click_element(driver, By.XPATH, "//div[contains(@class, 'service-name') and contains(text(), 'Registrations (New, Transfer, Out of State)')]")
    print("Clicked 'Registrations (New, Transfer, Out of State)'")
    print("Navigation to service selection complete.")

def get_available_locations(driver):
    """Gets a list of available DMV locations."""
    print("Fetching available locations...")
    try:
        location_elements = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class,'location-name-container')]//div[contains(@class,'location-name')]"))
        )
        locations = [loc.text.strip() for loc in location_elements if loc.text.strip()]
        if not locations:
            print("No locations found. The page structure might have changed.")
            return []
        print(f"Found locations: {locations}")
        return locations
    except TimeoutException:
        print("Error: Could not find location elements on the page.")
        return []
    except Exception as e:
        print(f"Error fetching locations: {e}")
        return []

def check_location_appointments(driver, location_name):
    """Checks a specific location for appointments within the next DAYS_TO_CHECK."""
    print(f"Checking appointments for: {location_name}")
    found_appointments = []

    try:
        # Click on the location
        click_element(driver, By.XPATH, f"//div[contains(@class,'location-name') and contains(text(),'{location_name}')]/ancestor::button")
        print(f"Clicked location: {location_name}")
    except Exception as e:
        print(f"Could not click on location {location_name}. It might be unavailable or there's a page load issue.")
        # Attempt to go back to location selection if possible
        try:
            back_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Back to Locations') or contains(text(), 'Change Location')]")
            back_button.click()
            time.sleep(1)
        except NoSuchElementException:
            print("Could not find a button to go back to location selection.")
        return found_appointments # Skip this location

    time.sleep(2) # Wait for calendar to potentially load

    today = datetime.now()
    for i in range(DAYS_TO_CHECK + 1): # Check today + next DAYS_TO_CHECK days
        current_date = today + timedelta(days=i)
        # Skip weekends (Saturday=5, Sunday=6)
        if current_date.weekday() >= 5:
            print(f"Skipping weekend: {current_date.strftime('%Y-%m-%d')}")
            continue

        print(f"Checking date: {current_date.strftime('%Y-%m-%d')}")

        # Navigate calendar if necessary (the site seems to show one month at a time)
        # Check if the current month/year of the calendar matches current_date
        try:
            calendar_header_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'p-datepicker-title')]"))
            )
            calendar_month_year_str = calendar_header_element.text.strip() # e.g., "July 2024"
            calendar_month_year = datetime.strptime(calendar_month_year_str, "%B %Y")

            while calendar_month_year.year < current_date.year or \
                  (calendar_month_year.year == current_date.year and calendar_month_year.month < current_date.month):
                print(f"Navigating to next month. Calendar shows: {calendar_month_year_str}, Target: {current_date.strftime('%B %Y')}")
                click_element(driver, By.XPATH, "//button[contains(@class,'p-datepicker-next')]")
                time.sleep(0.5) # Brief pause for calendar update
                calendar_header_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'p-datepicker-title')]"))
                )
                calendar_month_year_str = calendar_header_element.text.strip()
                calendar_month_year = datetime.strptime(calendar_month_year_str, "%B %Y")

        except TimeoutException:
            print("Could not find calendar header to verify month/year. Proceeding with current view.")
        except Exception as e:
            print(f"Error navigating calendar: {e}")
            # Continue trying to find dates in the current view


        # Find date cells that are not disabled and match the day
        date_xpath = f"//span[contains(@class,'p-datepicker-day') and not(contains(@class,'p-disabled')) and text()='{current_date.day}']"

        try:
            available_date_elements = driver.find_elements(By.XPATH, date_xpath)
            if not available_date_elements:
                print(f"No available slots for {location_name} on {current_date.strftime('%Y-%m-%d')} (day {current_date.day}).")
                continue

            for date_element in available_date_elements:
                # Ensure the date belongs to the current month, not previous/next month's preview
                parent_td = date_element.find_element(By.XPATH, "..")
                if 'p-datepicker-other-month' in parent_td.get_attribute('class'):
                    continue

                try:
                    date_element.click()
                    print(f"Clicked date {current_date.strftime('%Y-%m-%d')} for {location_name}")
                    time.sleep(2) # Wait for time slots to load

                    # Check for available time slots
                    time_slot_elements = driver.find_elements(By.XPATH, "//div[contains(@class,'time-slot-container')]//button[not(@disabled)]//div[contains(@class,'time-slot-time')]")

                    if time_slot_elements:
                        for slot_element in time_slot_elements:
                            slot_time = slot_element.text.strip()
                            appointment_info = f"APPOINTMENT FOUND: {location_name} on {current_date.strftime('%A, %B %d, %Y')} at {slot_time}"
                            print(appointment_info)
                            found_appointments.append(appointment_info)
                        # Once slots are found for a day, no need to click other identical day numbers (if any)
                        break
                    else:
                        print(f"No time slots found for {location_name} on {current_date.strftime('%Y-%m-%d')} after clicking date.")
                        # Go back to calendar view by trying to click the date again (if it exists)
                        # This is a bit of a hack; site behavior might vary
                        try:
                            re_click_date = driver.find_element(By.XPATH, date_xpath)
                            re_click_date.click() # to deselect or refresh
                            time.sleep(0.5)
                        except:
                            pass


                except Exception as e:
                    print(f"Error when clicking date {current_date.day} or processing slots for {location_name}: {e}")
                # Break from iterating date_elements if appointments are found for this day
                if found_appointments and any(current_date.strftime('%A, %B %d, %Y') in appt for appt in found_appointments):
                    break
            if found_appointments and any(current_date.strftime('%A, %B %d, %Y') in appt for appt in found_appointments):
                    print(f"Finished checking {current_date.strftime('%Y-%m-%d')} for {location_name} as appointments were found.")

        except NoSuchElementException:
            print(f"No available slots for {location_name} on {current_date.strftime('%Y-%m-%d')} (day {current_date.day}).")
        except Exception as e:
            print(f"General error checking date {current_date.strftime('%Y-%m-%d')} for {location_name}: {e}")


    # After checking all dates for a location, go back to the location selection page
    try:
        print(f"Trying to go back to location selection from {location_name} calendar.")
        # The "Back to Locations" or similar button might appear after selecting a location
        # Or, if already on calendar, a "Change Location" or "Back" button to service type then location
        # This site's navigation can be tricky. Let's try a general back button first if specific one fails.
        # Common text for such buttons: "Change Location", "Back to Locations", or a general "Back"
        # It seems after clicking a location, you land on its calendar.
        # We need to go back to the list of locations.
        # The "Schedule an Appointment" takes you to categories, then services, then locations.
        # So, we might need to re-navigate if a direct "back to locations" isn't obvious.

        # Try clicking the "Services" breadcrumb or a similar navigation element
        # This is an assumption based on typical web navigation patterns.
        # Update: The site has a "Back" button on the calendar page that usually takes you to location list.
        # Let's look for a button that would take us back to the location list.
        # The class "p-button-link" and "ng-star-inserted" seems to be used for back type buttons.
        # Or, a button with text "Change Location" or similar.

        # Attempt 1: Look for a "Change Location" button (if present on calendar page)
        change_location_button = driver.find_elements(By.XPATH, "//button[contains(., 'Change Location')]")
        if change_location_button:
            change_location_button[0].click()
            print("Clicked 'Change Location' button.")
            time.sleep(2)
            return found_appointments

        # Attempt 2: Look for a general "Back" button that might lead to location list
        # This is highly dependent on the current page state.
        # The "Back" button on the calendar page itself.
        back_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'p-button-link') and .//span[contains(text(), 'Back')]] | //button[contains(text(),'Back')]")
        if back_buttons:
            # Prefer a more specific back if available
            specific_back = [b for b in back_buttons if "Locations" in b.text or "Services" in b.text]
            if specific_back:
                specific_back[0].click()
                print("Clicked a specific 'Back' button.")
            else:
                # Try the most generic one, usually the first one found if it's simple "Back"
                back_buttons[0].click()
                print("Clicked a generic 'Back' button.")
            time.sleep(2)
        else:
            print("No obvious 'Back' or 'Change Location' button found. Re-navigating from start for next location.")
            # If all else fails, re-navigate from the start (this is inefficient but robust)
            # This part is removed to avoid re-navigation for each location if back fails once
            # as it makes the script very slow. The main loop will handle re-navigation if needed.
            pass

    except Exception as e:
        print(f"Error trying to navigate back to location selection from {location_name}: {e}")
        # If back navigation fails, the next call to get_available_locations might fail or the script might get stuck.
        # Consider re-navigating from scratch if this becomes a persistent issue.
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
            try:
                WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'location-name-container')]"))
                )
                print("Currently on location selection page.")
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
