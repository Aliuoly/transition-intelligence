"""Browser-side linking between AI event claims and the Plotly trend workspace."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import streamlit as st

EVENT_MARKER = re.compile(
    r"<!--event:(?P<transition_id>TR-[0-9]{2}):"
    r"(?P<start_hour>-?[0-9]+(?:\.[0-9]+)?):"
    r"(?P<end_hour>-?[0-9]+(?:\.[0-9]+)?)-->"
)


@dataclass(frozen=True)
class InteractiveAnswer:
    before: str
    claims: tuple[dict[str, Any], ...]
    after: str


def _plain_claim(markdown: str) -> str:
    text = re.sub(r"^\s*[-*]\s+", "", markdown)
    text = re.sub(r"\*\*|__|`", "", text)
    return text.strip()


def parse_interactive_answer(content: str) -> InteractiveAnswer:
    """Extract event-linked transcript bullets from an agent Markdown answer."""
    lines = content.splitlines()
    claim_indexes = [index for index, line in enumerate(lines) if EVENT_MARKER.search(line)]
    if not claim_indexes:
        return InteractiveAnswer(content, (), "")

    heading_index = claim_indexes[0]
    for index in range(claim_indexes[0] - 1, max(-1, claim_indexes[0] - 4), -1):
        if "notable event transcript" in lines[index].lower():
            heading_index = index
            break

    claims: list[dict[str, Any]] = []
    for index in claim_indexes:
        line = lines[index]
        references = [
            {
                "transition_id": match.group("transition_id"),
                "start_hour": float(match.group("start_hour")),
                "end_hour": float(match.group("end_hour")),
            }
            for match in EVENT_MARKER.finditer(line)
        ]
        visible_text = EVENT_MARKER.sub("", line)
        claims.append({"text": _plain_claim(visible_text), "references": references})

    end_index = claim_indexes[-1] + 1
    while end_index < len(lines) and not lines[end_index].strip():
        end_index += 1
    return InteractiveAnswer(
        "\n".join(lines[:heading_index]).strip(),
        tuple(claims),
        "\n".join(lines[end_index:]).strip(),
    )


_EVENT_CLAIMS = st.components.v2.component(
    "transition_event_claims",
    html='<section class="event-claims"><div class="event-claims-list"></div></section>',
    css="""
.event-claims {
  color: var(--st-text-color);
  font-family: var(--st-font);
  margin: 0.35rem 0 0.8rem;
}
.event-claims-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.35rem;
}
.event-claims-title {
  font-size: 0.92rem;
  font-weight: 650;
}
.event-claims-hint {
  color: color-mix(in srgb, var(--st-text-color) 58%, transparent);
  font-size: 0.68rem;
  white-space: nowrap;
}
.event-claim {
  background: color-mix(in srgb, var(--st-secondary-background-color) 72%, transparent);
  border: 1px solid color-mix(in srgb, var(--st-text-color) 13%, transparent);
  border-left: 3px solid var(--event-color, var(--st-primary-color));
  border-radius: 0.35rem;
  cursor: crosshair;
  font-size: 0.78rem;
  line-height: 1.35;
  margin: 0.28rem 0;
  padding: 0.44rem 0.55rem;
  transition: background 100ms ease, border-color 100ms ease, transform 100ms ease;
}
.event-claim:hover, .event-claim:focus-visible, .event-claim[data-pinned="true"] {
  background: color-mix(in srgb, var(--event-color, var(--st-primary-color)) 12%, var(--st-secondary-background-color));
  border-color: color-mix(in srgb, var(--event-color, var(--st-primary-color)) 48%, transparent);
  outline: none;
  transform: translateX(2px);
}
""",
    js="""
export default function(component) {
  const { data, parentElement } = component
  const section = parentElement.querySelector('.event-claims')
  const list = parentElement.querySelector('.event-claims-list')
  if (!section || !list) return

  section.querySelector('.event-claims-header')?.remove()
  const header = document.createElement('div')
  header.className = 'event-claims-header'
  const title = document.createElement('div')
  title.className = 'event-claims-title'
  title.textContent = 'Notable event transcript'
  const hint = document.createElement('div')
  hint.className = 'event-claims-hint'
  hint.textContent = 'Hover to inspect · click to pin'
  header.append(title, hint)
  section.prepend(header)
  list.replaceChildren()

  let pinned = null
  const publish = (claim) => window.dispatchEvent(new CustomEvent(
    'transition-event-highlight', { detail: claim }
  ))

  for (const [index, claim] of (data?.claims ?? []).entries()) {
    const row = document.createElement('div')
    row.className = 'event-claim'
    row.tabIndex = 0
    row.textContent = claim.text
    const firstId = claim.references?.[0]?.transition_id
    row.style.setProperty('--event-color', data?.colors?.[firstId] ?? '#087f5b')

    row.onmouseenter = () => publish(claim)
    row.onfocus = () => publish(claim)
    row.onmouseleave = () => { if (pinned !== index) publish(null) }
    row.onblur = () => { if (pinned !== index) publish(null) }
    row.onclick = () => {
      for (const item of list.querySelectorAll('.event-claim')) item.dataset.pinned = 'false'
      if (pinned === index) {
        pinned = null
        publish(null)
      } else {
        pinned = index
        row.dataset.pinned = 'true'
        publish(claim)
      }
    }
    list.append(row)
  }

  return () => publish(null)
}
""",
)


_CHART_BRIDGE = st.components.v2.component(
    "transition_event_chart_bridge",
    html='<span class="event-chart-bridge" aria-hidden="true"></span>',
    css="""
.event-chart-bridge { display: block; height: 0; overflow: visible; }
""",
    js="""
export default function(component) {
  const { data } = component
  const overlayId = `event-overlay-${data?.chart_key ?? 'trends'}`

  const removeOverlay = () => document.getElementById(overlayId)?.remove()
  const axisFor = (layout, reference, prefix) => {
    const suffix = reference && reference !== prefix ? reference.slice(1) : ''
    return layout[`${prefix}axis${suffix}`]
  }
  const numeric = (value) => typeof value === 'number' && Number.isFinite(value)

  let activeClaim = null
  const drawHighlight = (claim) => {
    removeOverlay()
    if (!claim?.references?.length) return
    const selector = `.st-key-${CSS.escape(data.chart_key)} .js-plotly-plot`
    const graph = document.querySelector(selector)
    if (!graph?._fullLayout || !graph?._fullData) return
    const bounds = graph.getBoundingClientRect()

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.id = overlayId
    Object.assign(svg.style, {
      position: 'fixed', inset: '0', width: '100vw', height: '100vh',
      pointerEvents: 'none', zIndex: '999'
    })

    for (const reference of claim.references) {
      const color = data.colors?.[reference.transition_id] ?? '#087f5b'
      const midpoint = (reference.start_hour + reference.end_hour) / 2
      const subplotPairs = new Map()

      for (const trace of graph._fullData) {
        if (trace.visible === false || trace.visible === 'legendonly') continue
        if (trace.meta?.transition_id !== reference.transition_id) continue
        const xref = trace.xaxis ?? 'x'
        const yref = trace.yaxis ?? 'y'
        subplotPairs.set(`${xref}:${yref}`, [xref, yref])

        const xaxis = axisFor(graph._fullLayout, xref, 'x')
        const yaxis = axisFor(graph._fullLayout, yref, 'y')
        const xs = trace.x ?? []
        const ys = trace.y ?? []
        if (!xaxis?.l2p || !yaxis?.l2p || !xs.length || xs.length !== ys.length) continue
        let nearest = -1
        let distance = Infinity
        for (let i = 0; i < xs.length; i += 1) {
          const x = Number(xs[i])
          const y = Number(ys[i])
          if (!numeric(x) || !numeric(y)) continue
          const nextDistance = Math.abs(x - midpoint)
          if (nextDistance < distance) { distance = nextDistance; nearest = i }
        }
        if (nearest < 0) continue
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
        circle.setAttribute('cx', bounds.left + xaxis._offset + xaxis.l2p(Number(xs[nearest])))
        circle.setAttribute('cy', bounds.top + yaxis._offset + yaxis.l2p(Number(ys[nearest])))
        circle.setAttribute('r', '4')
        circle.setAttribute('fill', 'white')
        circle.setAttribute('stroke', color)
        circle.setAttribute('stroke-width', '2.5')
        svg.append(circle)
      }

      for (const [xref, yref] of subplotPairs.values()) {
        const xaxis = axisFor(graph._fullLayout, xref, 'x')
        const yaxis = axisFor(graph._fullLayout, yref, 'y')
        if (!xaxis?.l2p || !yaxis) continue
        const startX = bounds.left + xaxis._offset + xaxis.l2p(reference.start_hour)
        const endX = bounds.left + xaxis._offset + xaxis.l2p(reference.end_hour)
        const width = Math.abs(endX - startX)
        if (width > 2) {
          const band = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
          band.setAttribute('x', Math.min(startX, endX))
          band.setAttribute('y', bounds.top + yaxis._offset)
          band.setAttribute('width', Math.max(2, width))
          band.setAttribute('height', yaxis._length)
          band.setAttribute('fill', color)
          band.setAttribute('fill-opacity', '0.10')
          band.setAttribute('stroke', color)
          band.setAttribute('stroke-opacity', '0.55')
          svg.prepend(band)
        } else {
          const line = document.createElementNS('http://www.w3.org/2000/svg', 'line')
          line.setAttribute('x1', startX)
          line.setAttribute('x2', startX)
          line.setAttribute('y1', bounds.top + yaxis._offset)
          line.setAttribute('y2', bounds.top + yaxis._offset + yaxis._length)
          line.setAttribute('stroke', color)
          line.setAttribute('stroke-width', '2')
          line.setAttribute('stroke-dasharray', '4 3')
          svg.prepend(line)
        }
      }
    }
    document.body.append(svg)
  }

  const renderHighlight = (event) => {
    activeClaim = event.detail
    drawHighlight(activeClaim)
  }
  const repositionHighlight = () => {
    if (activeClaim) window.requestAnimationFrame(() => drawHighlight(activeClaim))
    else removeOverlay()
  }

  window.addEventListener('transition-event-highlight', renderHighlight)
  window.addEventListener('resize', repositionHighlight)
  window.addEventListener('scroll', repositionHighlight, true)
  return () => {
    window.removeEventListener('transition-event-highlight', renderHighlight)
    window.removeEventListener('resize', repositionHighlight)
    window.removeEventListener('scroll', repositionHighlight, true)
    removeOverlay()
  }
}
""",
)


def render_interactive_answer(content: str, colors: dict[str, str]) -> None:
    parsed = parse_interactive_answer(content)
    if not parsed.claims:
        st.markdown(content)
        return
    if parsed.before:
        st.markdown(parsed.before)
    _EVENT_CLAIMS(data={"claims": list(parsed.claims), "colors": colors}, height="content")
    if parsed.after:
        st.markdown(parsed.after)


def render_chart_event_bridge(chart_key: str, colors: dict[str, str]) -> None:
    _CHART_BRIDGE(
        key=f"event-bridge-{chart_key}",
        data={"chart_key": chart_key, "colors": colors},
        height=0,
    )
