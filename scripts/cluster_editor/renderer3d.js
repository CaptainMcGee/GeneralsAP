/* Archipelago Cluster Placement Editor — Three.js 3D Preview Panel */
"use strict";

(function() {
  // ── Three.js availability check ──────────────────────────────────────────────
  if (typeof THREE === "undefined") {
    console.warn("renderer3d: THREE.js not loaded, 3D preview disabled");
    return;
  }

  const panelEl = document.getElementById("panel-3d");
  if (!panelEl) return;

  // ── Scene setup ────────────────────────────────────────────────────────────
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x111111);

  const camera = new THREE.PerspectiveCamera(50, 1, 1, 10000);
  camera.position.set(700, 1200, 1000);
  camera.lookAt(700, 700, 0);

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    panelEl.appendChild(renderer.domElement);
  } catch (e) {
    console.warn("renderer3d: WebGL not available", e);
    return;
  }

  // ── OrbitControls ──────────────────────────────────────────────────────────
  let controls;
  if (typeof THREE.OrbitControls !== "undefined") {
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.target.set(700, 700, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    controls.maxPolarAngle = Math.PI * 0.48;
    controls.minDistance = 200;
    controls.maxDistance = 4000;
    controls.addEventListener("change", () => needsRender = true);
  }

  // ── Lighting ───────────────────────────────────────────────────────────────
  scene.add(new THREE.AmbientLight(0xcccccc, 0.8));
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
  dirLight.position.set(500, 200, 800);
  scene.add(dirLight);

  // ── State ──────────────────────────────────────────────────────────────────
  let groundMesh = null;
  let groundTexture = null;
  let currentMapId = null;
  let clusterMeshes = [];   // { cone, spreadRing, defendRing, chaseRing, clusterId }
  let waypointMeshes = [];
  let needsRender = true;
  let animFrameId = null;

  const TIER_COLORS_3D = {
    easy:   0x4CAF50,
    medium: 0xFF9800,
    hard:   0xF44336,
  };

  // ── Ground plane ───────────────────────────────────────────────────────────
  function createGround(mapMeta) {
    // Remove old ground
    if (groundMesh) {
      scene.remove(groundMesh);
      groundMesh.geometry.dispose();
      if (groundMesh.material.map) groundMesh.material.map.dispose();
      groundMesh.material.dispose();
      groundMesh = null;
    }

    const w = mapMeta.map_world_size[0];
    const h = mapMeta.map_world_size[1];

    const geom = new THREE.PlaneGeometry(w, h);
    // Plane is in XY, looking up along Z — we keep that convention
    // (x → right, y → into the screen from top-down, z → up)

    let mat;
    if (groundTexture) {
      mat = new THREE.MeshLambertMaterial({ map: groundTexture, side: THREE.DoubleSide });
    } else {
      mat = new THREE.MeshLambertMaterial({ color: 0x1a331a, side: THREE.DoubleSide });
    }

    groundMesh = new THREE.Mesh(geom, mat);
    // Center the plane at (w/2, h/2, 0) — matching editor world coords
    groundMesh.position.set(w / 2, h / 2, 0);
    scene.add(groundMesh);
  }

  function loadGroundTexture(mapMeta) {
    const loader = new THREE.TextureLoader();
    loader.load(
      `maps/${mapMeta.image}`,
      (tex) => {
        tex.minFilter = THREE.LinearFilter;
        tex.magFilter = THREE.LinearFilter;
        groundTexture = tex;
        createGround(mapMeta);
        needsRender = true;
      },
      undefined,
      () => {
        // Image not available — use plain color
        groundTexture = null;
        createGround(mapMeta);
        needsRender = true;
      }
    );
  }

  // ── Ring helper ────────────────────────────────────────────────────────────
  function createRing(radius, color, opacity, dashed) {
    const segments = 48;
    const points = [];
    for (let i = 0; i <= segments; i++) {
      const a = (i / segments) * Math.PI * 2;
      points.push(new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, 0));
    }
    const geom = new THREE.BufferGeometry().setFromPoints(points);

    let mat;
    if (dashed) {
      mat = new THREE.LineDashedMaterial({
        color,
        opacity,
        transparent: opacity < 1,
        dashSize: 15,
        gapSize: 8,
      });
      const line = new THREE.Line(geom, mat);
      line.computeLineDistances();
      return line;
    }
    mat = new THREE.LineBasicMaterial({ color, opacity, transparent: opacity < 1 });
    return new THREE.Line(geom, mat);
  }

  // ── Cone / cylinder marker ─────────────────────────────────────────────────
  function createMarker(tier, isSelected) {
    const color = TIER_COLORS_3D[tier] || 0xFF9800;
    const h = isSelected ? 50 : 35;
    const r = isSelected ? 14 : 10;
    const geom = new THREE.ConeGeometry(r, h, 8);
    const mat = new THREE.MeshLambertMaterial({
      color,
      emissive: isSelected ? color : 0x000000,
      emissiveIntensity: isSelected ? 0.4 : 0,
    });
    const mesh = new THREE.Mesh(geom, mat);
    // Cone points up (along +Z in our orientation)
    mesh.rotation.x = Math.PI / 2;
    mesh.position.z = h / 2 + 2;
    return mesh;
  }

  // ── Waypoint diamond ───────────────────────────────────────────────────────
  function createWaypointMarker() {
    const geom = new THREE.OctahedronGeometry(12, 0);
    const mat = new THREE.MeshLambertMaterial({ color: 0x00BFFF, emissive: 0x003366, emissiveIntensity: 0.3 });
    const mesh = new THREE.Mesh(geom, mat);
    mesh.position.z = 15;
    return mesh;
  }

  // ── Clear clusters from scene ──────────────────────────────────────────────
  function clearClusterMeshes() {
    for (const entry of clusterMeshes) {
      scene.remove(entry.group);
      entry.group.traverse((child) => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
      });
    }
    clusterMeshes = [];
  }

  function clearWaypointMeshes() {
    for (const m of waypointMeshes) {
      scene.remove(m);
      m.traverse((child) => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
      });
    }
    waypointMeshes = [];
  }

  // ── Rebuild 3D scene from editor state ─────────────────────────────────────
  function rebuild() {
    if (typeof state === "undefined" || !state.registry) return;

    const mapId = state.currentMapId;
    if (!mapId) return;

    const mapMeta = state.registry.maps.find(m => m.id === mapId);
    if (!mapMeta) return;

    // Reload ground if map changed
    if (currentMapId !== mapId) {
      currentMapId = mapId;
      loadGroundTexture(mapMeta);
      resetCamera(mapMeta);
    }

    // Rebuild cluster markers
    clearClusterMeshes();
    clearWaypointMeshes();

    const showRadii = state.show.radii;
    const clusters = state.maps[mapId]?.clusters || [];
    const seedDim = state.seedMode;

    for (let i = 0; i < clusters.length; i++) {
      const c = clusters[i];
      const isSel = (i === state.selectedIdx);
      const isDimmed = seedDim && !state.seedSelected.has(i);
      const tier = c.tier || "medium";
      const color = TIER_COLORS_3D[tier] || 0xFF9800;

      const group = new THREE.Group();
      group.position.set(c.x, c.y, 0);

      // Marker cone
      const marker = createMarker(tier, isSel);
      if (isDimmed) {
        marker.material.opacity = 0.25;
        marker.material.transparent = true;
      }
      group.add(marker);

      // Radius rings (on the ground plane, z=1 to avoid z-fighting)
      if (showRadii && !isDimmed) {
        const spread = c.spread || 100;
        const defend = c.defend_radius || 375;
        const chase = c.chase_radius || 500;

        const spreadRing = createRing(spread, color, 0.7, false);
        spreadRing.position.z = 1;
        group.add(spreadRing);

        const defendRing = createRing(defend, color, 0.35, true);
        defendRing.position.z = 1;
        group.add(defendRing);

        const chaseRing = createRing(chase, color, 0.2, true);
        chaseRing.position.z = 1;
        group.add(chaseRing);
      }

      scene.add(group);
      clusterMeshes.push({ group, clusterId: c.cluster_id, index: i });
    }

    // Waypoints
    if (state.show.waypoints && mapMeta.known_waypoints) {
      for (const [name, [wx, wy]] of Object.entries(mapMeta.known_waypoints)) {
        const wpMarker = createWaypointMarker();
        wpMarker.position.set(wx, wy, 15);
        scene.add(wpMarker);
        waypointMeshes.push(wpMarker);
      }
    }

    needsRender = true;
  }

  // ── Camera ─────────────────────────────────────────────────────────────────
  function resetCamera(mapMeta) {
    const w = mapMeta.map_world_size[0];
    const h = mapMeta.map_world_size[1];
    const cx = w / 2;
    const cy = h / 2;

    camera.position.set(cx, cy - 600, 900);
    camera.lookAt(cx, cy, 0);
    if (controls) {
      controls.target.set(cx, cy, 0);
      controls.update();
    }
    needsRender = true;
  }

  // ── Resize ─────────────────────────────────────────────────────────────────
  function resizeRenderer() {
    const w = panelEl.clientWidth;
    const h = panelEl.clientHeight;
    if (w <= 0 || h <= 0) return;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    needsRender = true;
  }

  // ── Render loop ────────────────────────────────────────────────────────────
  function renderLoop() {
    animFrameId = requestAnimationFrame(renderLoop);
    if (controls) controls.update();
    if (needsRender) {
      renderer.render(scene, camera);
      needsRender = false;
    }
  }

  // ── Click-to-select in 3D ──────────────────────────────────────────────────
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();

  renderer.domElement.addEventListener("click", (e) => {
    if (typeof state === "undefined") return;

    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    // Collect all cone meshes
    const targets = [];
    for (const entry of clusterMeshes) {
      entry.group.traverse((child) => {
        if (child.isMesh && child.geometry.type === "ConeGeometry") {
          targets.push({ mesh: child, index: entry.index });
        }
      });
    }

    const meshes = targets.map(t => t.mesh);
    const intersects = raycaster.intersectObjects(meshes, false);

    if (intersects.length > 0) {
      const hit = intersects[0].object;
      const target = targets.find(t => t.mesh === hit);
      if (target && typeof selectCluster === "function") {
        selectCluster(target.index);
      }
    }
  });

  // ── Public API (called from editor.js) ─────────────────────────────────────
  window.update3D = function() {
    rebuild();
  };

  window.init3D = function() {
    resizeRenderer();
    renderLoop();
  };

  // ── Bootstrap ──────────────────────────────────────────────────────────────
  const ro = new ResizeObserver(() => {
    resizeRenderer();
    needsRender = true;
  });
  ro.observe(panelEl);

  // Initial setup
  resizeRenderer();
  renderLoop();

})();
