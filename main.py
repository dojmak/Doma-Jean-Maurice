#!/usr/bin/env python3
"""Minimal client for Anthropic Managed Agent agent_011CaB33ynhvwmYZYYrppFdM."""

import sys

import anthropic

AGENT_ID = "agent_011CaB33ynhvwmYZYYrppFdM"
ENVIRONMENT_ID = "env_01EbiBND3cX8Rz9dmWy4kHJv"
USER_MESSAGE = "Hello! Please introduce yourself briefly."


def main() -> None:
    client = anthropic.Anthropic()

    session = client.beta.sessions.create(
        agent=AGENT_ID,
        environment_id=ENVIRONMENT_ID,
    )
    print(f"Session {session.id} created, status={session.status}\n", flush=True)

    # Open the stream before sending so no early events are missed.
    with client.beta.sessions.stream(session_id=session.id) as stream:
        client.beta.sessions.events.send(
            session_id=session.id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": USER_MESSAGE}],
                }
            ],
        )

        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        print(block.text, end="", flush=True)

            elif event.type == "session.status_idle":
                print()  # newline after streamed text
                # requires_action means the agent is waiting on a tool result;
                # any other stop_reason (end_turn, retries_exhausted) is terminal.
                if event.stop_reason.type != "requires_action":
                    break

            elif event.type == "session.status_terminated":
                print()
                break


if __name__ == "__main__":
    try:
        main()
    except anthropic.APIStatusError as e:
        print(f"\nAPI error {e.status_code}: {e.message}", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIConnectionError as e:
        print(f"\nConnection error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        sys.exit(1)
