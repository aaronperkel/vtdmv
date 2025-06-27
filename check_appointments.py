import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
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
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        print("Please ensure Chrome is installed and accessible.")
        print("You might need to install chromedriver manually or check your PATH if webdriver-manager fails.")
        raise
    return driver

def click_element(driver, by, value, timeout=20):
    """Waits for an element to be clickable and then clicks it."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
        element.click()
        # General small delay after any click might be too broad.
        # Specific delays are handled in the main logic where page transitions are expected.
        # time.sleep(1)
    except TimeoutException:
        print(f"Error: Element with {by}='{value}' not found or clickable within {timeout} seconds.")
        raise
    except ElementClickInterceptedException as eci:
        print(f"Error clicking element {by}='{value}' due to interception: {eci}")
        print("Attempting JavaScript click as a fallback...")
        try:
            element = driver.find_element(by, value) # Re-find, it might be stale
            driver.execute_script("arguments[0].click();", element)
            print(f"Successfully clicked element {by}='{value}' using JavaScript.")
            # time.sleep(1) # Consider if JS click also needs a post-click delay
        except Exception as e_js:
            print(f"JavaScript click for {by}='{value}' also failed: {e_js}")
            raise eci # Re-raise original interception exception if JS click fails
    except Exception as e:
        print(f"Error clicking element {by}='{value}': {e}")
        raise

def navigate_to_services(driver):
    """Navigates through the initial appointment scheduling steps."""
    print("Navigating to services...")
    driver.get(BASE_URL)
    time.sleep(1) # Initial page load

    # Click "Schedule an Appointment" button - this is actually a div
    click_element(driver, By.XPATH, "//div[contains(@class, 'serviceprofilelabel') and normalize-space(text())='Schedule an Appointment']/ancestor::div[contains(@class,'serviceprofilebutton')][1]")
    print("Clicked 'Schedule an Appointment' (div)")
    time.sleep(1.5)

    # Click "Registration/Title" service category
    click_element(driver, By.XPATH, "//div[contains(@class, 'QflowObjectItem') and contains(@class, 'displaydata-text') and @data-id='Registration/Title']")
    print("Clicked 'Registration/Title'")
    time.sleep(1.5)

    # Click "Registrations (New, Transfer, Out of State)" service
    click_element(driver, By.XPATH, "//div[contains(@class, 'QflowObjectItem') and contains(@class, 'displaydata-text') and @data-id='34-']")
    print("Clicked 'Registrations (New, Transfer, Out of State)' (data-id='34-')")
    time.sleep(1.5)

    print("Navigation to office selection complete.")

def get_available_locations(driver):
    """Gets a list of available DMV locations and their data-ids."""
    print("Fetching available locations...")
    locations_data = []
    try:
        location_elements_outers = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'QflowObjectItem') and contains(@class, 'displaydata-text') and @data-id]"))
        )
        if not location_elements_outers:
            print("No location elements found on office selection page.")
            return []

        for outer_div in location_elements_outers:
            data_id = outer_div.get_attribute("data-id")
            try:
                name_div = outer_div.find_element(By.XPATH, ".//div[contains(@class, 'center-textDiv')]")
                full_text = name_div.text.strip()
                location_name = full_text.split('\n')[0].strip()
                if location_name and data_id:
                    locations_data.append({"name": location_name, "data_id": data_id})
            except NoSuchElementException:
                print(f"Could not find name_div for an element with data-id {data_id}")
            except Exception as e_inner:
                print(f"Error processing a location element: {e_inner}")

        if not locations_data:
            print("No locations with names and data-ids processed successfully.")
        else:
            print(f"Found locations: {locations_data}")
        return locations_data
    except TimeoutException:
        print("Timeout: Could not find location elements on the page.")
        return []
    except Exception as e:
        print(f"Error fetching locations: {e}")
        return []

def check_location_appointments(driver, location_info):
    location_name = location_info["name"]
    location_data_id = location_info["data_id"]
    print(f"Checking appointments for: {location_name} (data-id: {location_data_id})")
    found_appointments = []

    try:
        click_element(driver, By.XPATH, f"//div[contains(@class, 'QflowObjectItem') and contains(@class, 'displaydata-text') and @data-id='{location_data_id}']")
        print(f"Clicked location: {location_name}")
        time.sleep(2) # Increased wait for calendar page to fully render
    except Exception as e:
        print(f"Could not click on location {location_name} (data-id: {location_data_id}): {e}")
        return found_appointments

    try:
        single_date_time_div = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "SingleDateTime"))
        )
        data_datetime_str = single_date_time_div.get_attribute("data-datetime")
        visible_text = single_date_time_div.text.strip()
        print(f"Found 'Next Available' div: {visible_text} (data: {data_datetime_str})")

        if data_datetime_str:
            try:
                appointment_dt = datetime.strptime(data_datetime_str, "%m/%d/%Y %I:%M:%S %p")
            except ValueError:
                try:
                    appointment_dt = datetime.strptime(data_datetime_str, "%m/%d/%Y %H:%M:%S")
                except ValueError as ve_fallback:
                    print(f"Could not parse data-datetime string '{data_datetime_str}': {ve_fallback}")
                    appointment_dt = None

            if appointment_dt:
                now = datetime.now()
                if now.date() <= appointment_dt.date() <= (now + timedelta(days=DAYS_TO_CHECK)).date():
                    if appointment_dt.weekday() < 5: # Monday=0, Sunday=6
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
        print(f"No 'Next Available' (SingleDateTime div) found for {location_name} within 10 seconds. Fallback calendar check is disabled.")
    except NoSuchElementException:
        print(f"No 'Next Available' (SingleDateTime div) found for {location_name}. Assuming no quick appointment.")
    except Exception as e:
        print(f"Error checking SingleDateTime div for {location_name}: {e}")

    # Navigate back to the office selection page
    try:
        print(f"Trying to go back to office selection from {location_name}'s date/time page.")
        overlay_xpath = "//div[contains(@class,'blockUI') and contains(@class,'blockOverlay')]"
        try:
            WebDriverWait(driver, 10).until(
                EC.invisibility_of_element_located((By.XPATH, overlay_xpath))
            )
            print("blockUI overlay is not visible before attempting BackButton click.")
        except TimeoutException:
            print("blockUI overlay still visible after 10 seconds before BackButton click. Proceeding cautiously.")

        back_button_id = "BackButton"
        back_button_element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, back_button_id))
        )
        try:
            back_button_element.click()
            print(f"Clicked '{back_button_id}' button via standard click.")
        except ElementClickInterceptedException:
            print(f"Standard click on '{back_button_id}' was intercepted. Trying JavaScript click.")
            # Re-fetch element if stale, though it should be the same one from WebDriverWait
            js_back_button = driver.find_element(By.ID, back_button_id)
            driver.execute_script("arguments[0].click();", js_back_button)
            print(f"Clicked '{back_button_id}' button via JavaScript.")

        time.sleep(1.5)
    except Exception as e:
        print(f"Error navigating back from {location_name}'s page: {e}")
        # If back fails, the main loop's page check will attempt recovery.
    return found_appointments

def main():
    driver = None
    all_found_appointments = []
    try:
        driver = setup_driver()
        navigate_to_services(driver)

        locations = get_available_locations(driver)
        if not locations:
            print("No locations were found after initial navigation. Exiting.")
            return

        for i, loc_info in enumerate(locations):
            print(f"\nProcessing location {i+1}/{len(locations)}: {loc_info['name']}")

            # Check if we are on the office selection page before processing each location.
            # This is important because back navigation might fail.
            try:
                WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'QflowObjectItem') and contains(@class, 'displaydata-text') and @data-id]"))
                )
                print("Currently on office selection page.")
            except TimeoutException:
                print("Not on office selection page. Attempting to re-navigate from services...")
                try:
                    navigate_to_services(driver) # This will bring us back to office selection
                    # Re-fetch locations if navigation was reset
                    current_locations_on_page_check = get_available_locations(driver)
                    if not any(l['data_id'] == loc_info['data_id'] for l in current_locations_on_page_check):
                        print(f"Location {loc_info['name']} not found after re-navigation. Skipping.")
                        continue
                    print("Re-navigation successful, now on office selection page.")
                except Exception as e_recovery:
                    print(f"Failed to re-navigate to office selection: {e_recovery}. Skipping remaining locations.")
                    break

            appointments = check_location_appointments(driver, loc_info)
            all_found_appointments.extend(appointments)

        if not all_found_appointments:
            print("\nNo appointments found in any location for the specified dates.")
        else:
            print("\n--- Summary of Found Appointments ---")
            for appt in all_found_appointments:
                print(appt)

    except Exception as e:
        print(f"An critical error occurred in main: {e}")
    finally:
        if driver:
            print("Closing browser.")
            driver.quit()

if __name__ == "__main__":
    main()
