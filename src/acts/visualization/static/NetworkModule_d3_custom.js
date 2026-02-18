const NetworkModule = function (svg_width, svg_height) {
  const svg = d3.create("svg");
  svg
    .attr("class", "NetworkModule_d3")
    .attr("width", svg_width)
    .attr("height", svg_height)
    .style("border", "1px dotted");

  document.getElementById("elements").appendChild(svg.node());

  const width = +svg.attr("width");
  const height = +svg.attr("height");
  const g = svg
    .append("g")
    .classed("network_root", true);

  const tooltip = d3
    .select("body")
    .append("div")
    .attr("class", "d3tooltip")
    .style("opacity", 0);

  const zoom = d3.zoom()
    .on("zoom", (event) => {
      g.attr("transform", event.transform);
    });

  svg.call(zoom);

  svg.call(
    zoom.transform,
    d3.zoomIdentity.translate(width / 2, height / 2)
  );

  const defs = svg.append("defs");
  defs
    .append("marker")
    .attr("id", "edge-arrow")
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 10)
    .attr("refY", 0)
    .attr("markerWidth", 6)
    .attr("markerHeight", 6)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "#000000");

  const links = g.append("g").attr("class", "links");
  const intersectionGroups = g.append("g").attr("class", "intersection-groups");
  const nodes = g.append("g").attr("class", "nodes");
  const vehicles = g.append("g").attr("class", "vehicles");

  this.render = (data) => {
    const graph = JSON.parse(JSON.stringify(data));

    const positionedNodes = graph.nodes.filter(
      (node) => Number.isFinite(node.x) && Number.isFinite(node.y)
    );

    if (positionedNodes.length > 0) {
      const minX = d3.min(positionedNodes, (node) => node.x);
      const maxX = d3.max(positionedNodes, (node) => node.x);
      const minY = d3.min(positionedNodes, (node) => node.y);
      const maxY = d3.max(positionedNodes, (node) => node.y);

      const spanX = maxX - minX;
      const spanY = maxY - minY;

      const padding = 40;
      const canvasWidth = width - 2 * padding;
      const canvasHeight = height - 2 * padding;

      const scaleX = spanX > 0 ? canvasWidth / spanX : 1;
      const scaleY = spanY > 0 ? canvasHeight / spanY : 1;
      const scale = Math.min(scaleX, scaleY);

      const centerX = (minX + maxX) / 2;
      const centerY = (minY + maxY) / 2;

      graph.nodes.forEach((node) => {
        if (Number.isFinite(node.x) && Number.isFinite(node.y)) {
          node.fx = node.x;
          node.fy = node.y;
          node.renderX = (node.x - centerX) * scale;
          node.renderY = (node.y - centerY) * scale;
        } else {
          node.renderX = 0;
          node.renderY = 0;
        }
      });
    } else {
      graph.nodes.forEach((node) => {
        node.renderX = Number.isFinite(node.x) ? node.x : 0;
        node.renderY = Number.isFinite(node.y) ? node.y : 0;
      });
    }

    const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
    const edgeByDirection = new Map();

    graph.edges.forEach((edge) => {
      const sourceNode =
        typeof edge.source === "object" ? edge.source : nodeById.get(edge.source);
      const targetNode =
        typeof edge.target === "object" ? edge.target : nodeById.get(edge.target);

      edge.sourceNode = sourceNode;
      edge.targetNode = targetNode;
    });

    const laneSpacing = 5;
    const directedGroups = new Map();

    graph.edges.forEach((edge) => {
      if (!edge.sourceNode || !edge.targetNode) {
        return;
      }
      const sourceId = edge.sourceNode.id;
      const targetId = edge.targetNode.id;
      const directedKey = `${sourceId}->${targetId}`;
      if (!directedGroups.has(directedKey)) {
        directedGroups.set(directedKey, []);
      }
      directedGroups.get(directedKey).push(edge);
    });

    directedGroups.forEach((edges, directedKey) => {
      if (edges.length > 0) {
        edgeByDirection.set(directedKey, edges[0]);
      }
    });

    const hasReverseDirection = new Set();
    directedGroups.forEach((_, directedKey) => {
      const [sourceId, targetId] = directedKey.split("->");
      const reverseKey = `${targetId}->${sourceId}`;
      if (directedGroups.has(reverseKey)) {
        hasReverseDirection.add(directedKey);
      }
    });

    directedGroups.forEach((edges, directedKey) => {
      const hasReverse = hasReverseDirection.has(directedKey);
      const baseOffset = hasReverse ? laneSpacing / 2 : 0;
      const center = (edges.length - 1) / 2;
      edges.forEach((edge, index) => {
        const localOffset = (index - center) * laneSpacing;
        edge.parallelOffset = baseOffset + localOffset;
      });
    });

    graph.edges.forEach((edge) => {
      if (!edge.sourceNode || !edge.targetNode) {
        edge.renderX1 = 0;
        edge.renderY1 = 0;
        edge.renderX2 = 0;
        edge.renderY2 = 0;
        return;
      }

      const x1 = edge.sourceNode.renderX;
      const y1 = edge.sourceNode.renderY;
      const x2 = edge.targetNode.renderX;
      const y2 = edge.targetNode.renderY;

      const dx = x2 - x1;
      const dy = y2 - y1;
      const length = Math.sqrt(dx * dx + dy * dy);

      if (!Number.isFinite(length) || length === 0) {
        edge.renderX1 = x1;
        edge.renderY1 = y1;
        edge.renderX2 = x2;
        edge.renderY2 = y2;
        return;
      }

      const nx = -dy / length;
      const ny = dx / length;
      const signedOffset = Number.isFinite(edge.parallelOffset) ? edge.parallelOffset : 0;
      const offsetX = nx * signedOffset;
      const offsetY = ny * signedOffset;

      const shiftedX1 = x1 + offsetX;
      const shiftedY1 = y1 + offsetY;
      const shiftedX2 = x2 + offsetX;
      const shiftedY2 = y2 + offsetY;

      const shiftedDx = shiftedX2 - shiftedX1;
      const shiftedDy = shiftedY2 - shiftedY1;
      const shiftedLength = Math.sqrt(shiftedDx * shiftedDx + shiftedDy * shiftedDy);

      if (!Number.isFinite(shiftedLength) || shiftedLength === 0) {
        edge.renderX1 = shiftedX1;
        edge.renderY1 = shiftedY1;
        edge.renderX2 = shiftedX2;
        edge.renderY2 = shiftedY2;
        return;
      }

      const ux = shiftedDx / shiftedLength;
      const uy = shiftedDy / shiftedLength;
      const sourceRadius = Number.isFinite(edge.sourceNode.size) ? edge.sourceNode.size : 0;
      const targetRadius = Number.isFinite(edge.targetNode.size) ? edge.targetNode.size : 0;
      const startPadding = sourceRadius + 1;
      const endPadding = targetRadius + 3;

      edge.renderX1 = shiftedX1 + ux * startPadding;
      edge.renderY1 = shiftedY1 + uy * startPadding;
      edge.renderX2 = shiftedX2 - ux * endPadding;
      edge.renderY2 = shiftedY2 - uy * endPadding;
    });

    links.selectAll("line").data(graph.edges).enter().append("line");

    links
      .selectAll("line")
      .data(graph.edges)
      .attr("x1", function (d) {
        return Number.isFinite(d.renderX1) ? d.renderX1 : 0;
      })
      .attr("y1", function (d) {
        return Number.isFinite(d.renderY1) ? d.renderY1 : 0;
      })
      .attr("x2", function (d) {
        return Number.isFinite(d.renderX2) ? d.renderX2 : 0;
      })
      .attr("y2", function (d) {
        return Number.isFinite(d.renderY2) ? d.renderY2 : 0;
      })
      .attr("stroke-width", function (d) {
        return d.width;
      })
      .attr("stroke", function (d) {
        return d.color;
      })
      .attr("marker-end", function () {
        return "url(#edge-arrow)";
      });

    links.selectAll("line").data(graph.edges).exit().remove();

    const grouped = d3.group(
      graph.nodes.filter((node) => Number.isFinite(node.renderX) && Number.isFinite(node.renderY)),
      (node) => node.intersection
    );

    const groupData = Array.from(grouped, ([intersection, groupNodes]) => {
      if (intersection === undefined || groupNodes.length < 2) {
        return null;
      }
      const centerX = d3.mean(groupNodes, (n) => n.renderX);
      const centerY = d3.mean(groupNodes, (n) => n.renderY);
      const radius =
        d3.max(groupNodes, (n) => {
          const dx = n.renderX - centerX;
          const dy = n.renderY - centerY;
          return Math.sqrt(dx * dx + dy * dy);
        }) + 10;
      return {
        intersection,
        centerX,
        centerY,
        radius,
      };
    }).filter(Boolean);

    intersectionGroups.selectAll("circle").data(groupData, (d) => d.intersection)
      .enter()
      .append("circle")
      .attr("fill", "none")
      .attr("stroke", "#666666")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "4 3")
      .attr("data-intersection", (d) => d.intersection)
      .style("opacity", 0)
      .style("pointer-events", "stroke")
      .on("mouseover", function (event, d) {
        intersectionGroups
          .selectAll("circle")
          .filter((g) => g.intersection === d.intersection)
          .style("opacity", 1);
      })
      .on("mouseout", function () {
        intersectionGroups.selectAll("circle").style("opacity", 0);
      });

    intersectionGroups.selectAll("circle").data(groupData, (d) => d.intersection)
      .attr("cx", (d) => d.centerX)
      .attr("cy", (d) => d.centerY)
      .attr("r", (d) => d.radius)
      .attr("data-intersection", (d) => d.intersection);

    intersectionGroups.selectAll("circle").data(groupData, (d) => d.intersection).exit().remove();

    nodes
      .selectAll("circle")
      .data(graph.nodes)
      .enter()
      .append("circle")
      .on("mouseover", function (event, d) {
        tooltip.transition().duration(200).style("opacity", 0.9);
        tooltip
          .html(d.tooltip)
          .style("left", event.pageX + "px")
          .style("top", event.pageY + "px");
        if (d.intersection !== undefined) {
          intersectionGroups
            .selectAll("circle")
            .filter((g) => g.intersection === d.intersection)
            .style("opacity", 1);
        }
      })
      .on("mouseout", function () {
        tooltip.transition().duration(500).style("opacity", 0);
        intersectionGroups.selectAll("circle").style("opacity", 0);
      });

    nodes
      .selectAll("circle")
      .data(graph.nodes)
      .attr("cx", function (d) {
        return d.renderX;
      })
      .attr("cy", function (d) {
        return d.renderY;
      })
      .attr("r", function (d) {
        return d.size;
      })
      .attr("fill", function (d) {
        return d.color;
      });

    nodes.selectAll("circle").data(graph.nodes).exit().remove();

    const vehicleData = Array.isArray(graph.vehicles) ? graph.vehicles : [];

    const vehicleRenderData = vehicleData
      .map((vehicle) => {
        if (vehicle.mode === "edge") {
          const sourceNode = nodeById.get(vehicle.from);
          const targetNode = nodeById.get(vehicle.to);
          if (!sourceNode || !targetNode) {
            return null;
          }

          const x1 = sourceNode.renderX;
          const y1 = sourceNode.renderY;
          const x2 = targetNode.renderX;
          const y2 = targetNode.renderY;

          const dx = x2 - x1;
          const dy = y2 - y1;
          const length = Math.sqrt(dx * dx + dy * dy);
          if (!Number.isFinite(length) || length === 0) {
            return null;
          }

          const ux = dx / length;
          const uy = dy / length;
          const nx = -uy;
          const ny = ux;

          const edgeKey = `${vehicle.from}->${vehicle.to}`;
          const directionalEdge = edgeByDirection.get(edgeKey);
          const laneOffset = Number.isFinite(directionalEdge?.parallelOffset)
            ? directionalEdge.parallelOffset
            : (Number.isFinite(vehicle.laneOffset) ? vehicle.laneOffset : 0);

          const stopPadding = Number.isFinite(targetNode.size)
            ? targetNode.size + 8
            : 14;

          const progressRaw = Number.isFinite(vehicle.progress) ? vehicle.progress : 0;
          const progress = Math.min(Math.max(progressRaw, 0.02), 0.9);
          const maxTravel = Math.max(length - stopPadding, 0);
          const travel = progress * maxTravel;

          return {
            ...vehicle,
            renderX: x1 + ux * travel + nx * laneOffset,
            renderY: y1 + uy * travel + ny * laneOffset,
          };
        }

        const node = nodeById.get(vehicle.node);
        if (!node) {
          return null;
        }
        return {
          ...vehicle,
          renderX: node.renderX,
          renderY: node.renderY,
        };
      })
      .filter(Boolean);

    vehicles
      .selectAll("circle")
      .data(vehicleRenderData, (d) => d.id)
      .enter()
      .append("circle")
      .attr("r", 3.5)
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 1)
      .on("mouseover", function (event, d) {
        tooltip.transition().duration(120).style("opacity", 0.9);
        tooltip
          .html(d.tooltip || d.id)
          .style("left", event.pageX + "px")
          .style("top", event.pageY + "px");
      })
      .on("mouseout", function () {
        tooltip.transition().duration(220).style("opacity", 0);
      });

    vehicles
      .selectAll("circle")
      .data(vehicleRenderData, (d) => d.id)
      .attr("cx", (d) => d.renderX)
      .attr("cy", (d) => d.renderY)
      .attr("fill", (d) => (d.state === "DRIVING" ? "#1f77b4" : "#243b6b"));

    vehicles
      .selectAll("circle")
      .data(vehicleRenderData, (d) => d.id)
      .exit()
      .remove();
  };

  this.reset = () => {};
};
