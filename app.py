import os
import anthropic
from flask import Flask, Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# Holds the generated briefing until Twilio fetches it
current_briefing = {"text": "Good morning. Your briefing is not ready yet."}


def generate_briefing():
    """Call Claude with web search to write a morning briefing, then dial."""
    print("Generating briefing...")

    ai = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = ai.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{
            "role": "user",
            "content": (
                "You are calling Lindsay on the phone to wake her up. It's morning in Boston. "
                "Search for today's top news headlines and current Boston weather. "
                "Write a spoken morning briefing — under 90 seconds when read aloud. "
                "Tone: warm but no-nonsense. She needs to actually get out of bed. "
                "Structure: greet her by name, 3 news items with brief context, Boston weather, "
                "one short motivating push to get up. "
                "Write ONLY the spoken words — no markdown, no bullet points, no stage directions."
            )
        }]
    )

    # Pull text out of the response (web search tool use blocks have no .text)
    briefing_text = " ".join(
        block.text for block in response.content if hasattr(block, "text")
    ).strip()

    if not briefing_text:
        briefing_text = "Good morning Lindsay. Something went wrong generating your briefing. But you still need to get up."

    current_briefing["text"] = briefing_text
    print(f"Briefing ready: {briefing_text[:80]}...")

    make_call()


def make_call():
    """Trigger the Twilio outbound call."""
    twilio = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

    call = twilio.calls.create(
        to=os.environ["YOUR_PHONE_NUMBER"],
        from_=os.environ["TWILIO_PHONE_NUMBER"],
        url=f"{os.environ['APP_URL']}/twiml",
    )
    print(f"Call placed: {call.sid}")


@app.route("/twiml")
def twiml():
    """Twilio fetches this when the call connects — returns the spoken briefing."""
    response = VoiceResponse()
    response.say(current_briefing["text"], voice="Polly.Joanna", language="en-US")
    return Response(str(response), mimetype="text/xml")


@app.route("/trigger")
def trigger():
    """Manual trigger for testing — hit this in your browser to fire a call immediately."""
    generate_briefing()
    return "Call triggered! Check your phone.", 200


@app.route("/health")
def health():
    return "OK", 200


if __name__ == "__main__":
    wake_hour = int(os.environ.get("WAKE_HOUR", 7))
    wake_minute = int(os.environ.get("WAKE_MINUTE", 0))

    scheduler = BackgroundScheduler(timezone="America/New_York")
    scheduler.add_job(
        generate_briefing,
        "cron",
        hour=wake_hour,
        minute=wake_minute,
    )
    scheduler.start()
    print(f"Scheduler running — will call at {wake_hour}:{wake_minute:02d} ET daily.")

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
