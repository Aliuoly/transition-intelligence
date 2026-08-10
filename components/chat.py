"""Small browser behaviors for the Streamlit agent pane."""

from __future__ import annotations

import streamlit as st

_CHAT_AUTOSCROLL = st.components.v2.component(
    "transition_chat_autoscroll",
    html='<span class="chat-autoscroll" aria-hidden="true"></span>',
    css="""
.chat-autoscroll { display: block; height: 0; overflow: hidden; }
""",
    js="""
export default function(component) {
  const transcriptKey = component.data?.transcript_key ?? 'agent-transcript'
  const selector = `.st-key-${CSS.escape(transcriptKey)}`
  const transcript = document.querySelector(selector)
  if (!transcript) return

  let animationFrame = null
  const followResponse = () => {
    if (animationFrame !== null) window.cancelAnimationFrame(animationFrame)
    animationFrame = window.requestAnimationFrame(() => {
      transcript.scrollTop = transcript.scrollHeight
      animationFrame = null
    })
  }

  const mutationObserver = new MutationObserver(followResponse)
  mutationObserver.observe(transcript, {
    childList: true,
    subtree: true,
    characterData: true,
  })

  const resizeObserver = new ResizeObserver(followResponse)
  resizeObserver.observe(transcript)
  for (const child of transcript.children) resizeObserver.observe(child)
  followResponse()

  return () => {
    mutationObserver.disconnect()
    resizeObserver.disconnect()
    if (animationFrame !== null) window.cancelAnimationFrame(animationFrame)
  }
}
""",
)


def render_chat_autoscroll(transcript_key: str = "agent-transcript") -> None:
    """Keep a streaming transcript aligned with its newest content."""
    _CHAT_AUTOSCROLL(
        key=f"chat-autoscroll-{transcript_key}",
        data={"transcript_key": transcript_key},
        height=0,
    )
