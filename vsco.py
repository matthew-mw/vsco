import requests
import zipfile
import time

# Constants
API_BEARER_TOKEN = "7356455548d0a1d886db010883388d08be84d0c9"
ZIP_FILENAME = "vsco_images.zip"
HEADERS = {
    "Authorization": f"Bearer {API_BEARER_TOKEN}",
    "Accept": "*/*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
}

def get_site_id(username):
    """
    Get the site_id for a given VSCO username.
    
    :param username: The VSCO username.
    :return: The site_id for the given username.
    :raises requests.exceptions.HTTPError: If the API request fails.
    """
    url = "https://vsco.co/api/2.0/sites"  # Must be API v2.0 for site_id
    params = {"subdomain": username}
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    data = response.json()

    # The returned JSON should have a "sites" list; adjust keys if they differ in practice
    return data["sites"][0]["id"]

def get_with_exponential_backoff(url, headers=None, params=None, max_retries=5, backoff_factor=1.0):
    """
    Perform a GET request with exponential backoff.

    :param url: The URL for the HTTP GET request.
    :param headers: Optional HTTP headers.
    :param params: Optional query parameters.
    :param max_retries: Maximum number of retries before raising an exception.
    :param backoff_factor: Initial sleep time (in seconds); doubles after every failed attempt.
    :return: The requests.Response object if successful.
    :raises requests.exceptions.RequestException: If all retries fail.
    """
    attempt = 0
    sleep_time = backoff_factor

    while attempt < max_retries:
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response  # Success
        except requests.exceptions.RequestException as exc:
            attempt += 1
            print(f"[ERROR] Attempt {attempt} failed: {exc}")
            if attempt == max_retries:
                print("[ERROR] Maximum retry attempts reached. Raising exception.")
                raise
            print(f"[INFO] Retrying in {sleep_time:.1f} seconds...")
            time.sleep(sleep_time)
            sleep_time *= 2

def download_vsco_images(username):
    """
    Download all images from a VSCO user's profile and store them into a single ZIP file.

    :param username: The VSCO username.
    """
    site_id = get_site_id(username)
    params = {"cursor": "", "site_id": site_id}
    page_count = 0

    with zipfile.ZipFile(ZIP_FILENAME, "w", zipfile.ZIP_DEFLATED) as zipf:
        while True:
            page_count += 1
            print(f"Fetching page {page_count}, using cursor={params['cursor']}")

            # Fetch JSON data for the current page
            response = get_with_exponential_backoff(
                url="https://vsco.co/api/3.0/medias/profile",
                headers=HEADERS,
                params=params,
                max_retries=5,
                backoff_factor=1.0
            )
            data = response.json()

            # The JSON might differ. Adjust keys if needed based on actual API response.
            medias = data.get("media", [])
            next_cursor = data.get("next_cursor")

            if not medias or not next_cursor:
                # End pagination if there's no new media or no next cursor
                print("No more media or next_cursor. Pagination complete.")
                break

            # Update cursor for the next page
            params["cursor"] = next_cursor

            # Process each item
            for item in medias:
                try:
                    file_id = item["image"]["_id"]
                    image_url = f"https://{item['image']['responsive_url']}"
                except KeyError:
                    # If the JSON doesn't have the expected keys, skip this item
                    print("[WARNING] Unexpected JSON structure, skipping item.")
                    continue

                # Fetch image with exponential backoff
                try:
                    img_response = get_with_exponential_backoff(
                        url=image_url,
                        headers=HEADERS,
                        max_retries=5,
                        backoff_factor=1.0
                    )
                except requests.exceptions.RequestException as exc:
                    print(f"[ERROR] Could not fetch image {file_id}: {exc}")
                    continue

                # Write the image bytes to the ZIP archive
                zipf.writestr(f"{file_id}.jpg", img_response.content)
                print(f"Saved image {file_id}.jpg to ZIP.")

    print(f"All images zipped into {ZIP_FILENAME}")

if __name__ == "__main__":
    vsco_username = input("Enter VSCO username: ").strip()
    download_vsco_images(vsco_username)
