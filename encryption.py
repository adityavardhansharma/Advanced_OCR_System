from urllib.parse import quote_plus

username = "adityavardhansharma"
password = "Aditya18@"  # Contains characters needing encoding
encoded_password = quote_plus(password)
print(f"Encoded password: {encoded_password}")
