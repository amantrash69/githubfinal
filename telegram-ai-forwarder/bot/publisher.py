async def forward_message(client, message, target_id):
    """
    Sends the message exactly as it is to the target channel.
    Handles text, photos, and documents gracefully.
    """
    # Using client.send_message handles sending the text/media natively 
    # based on the original message object.
    await client.send_message(int(target_id), message)
