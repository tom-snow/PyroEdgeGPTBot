from base64 import b64encode

# Make sure you have the correct cookie file locally
with open("./cookie.json", "r", encoding="utf-8") as file:
    data = file.read()
    COOKIE = b64encode(bytes(data, "utf-8")).decode("utf-8")
    # print(COOKIE)
    with open("./base64_encoded_cookie.txt", "w", encoding="utf-8") as file:
        file.write(COOKIE)