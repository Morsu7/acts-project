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

  const links = g.append("g").attr("class", "links");
  const intersectionGroups = g.append("g").attr("class", "intersection-groups");
  const nodes = g.append("g").attr("class", "nodes");

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

    graph.edges.forEach((edge) => {
      const sourceNode =
        typeof edge.source === "object" ? edge.source : nodeById.get(edge.source);
      const targetNode =
        typeof edge.target === "object" ? edge.target : nodeById.get(edge.target);

      edge.sourceNode = sourceNode;
      edge.targetNode = targetNode;
    });

    links.selectAll("line").data(graph.edges).enter().append("line");

    links
      .selectAll("line")
      .data(graph.edges)
      .attr("x1", function (d) {
        return d.sourceNode ? d.sourceNode.renderX : 0;
      })
      .attr("y1", function (d) {
        return d.sourceNode ? d.sourceNode.renderY : 0;
      })
      .attr("x2", function (d) {
        return d.targetNode ? d.targetNode.renderX : 0;
      })
      .attr("y2", function (d) {
        return d.targetNode ? d.targetNode.renderY : 0;
      })
      .attr("stroke-width", function (d) {
        return d.width;
      })
      .attr("stroke", function (d) {
        return d.color;
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
  };

  this.reset = () => {};
};
