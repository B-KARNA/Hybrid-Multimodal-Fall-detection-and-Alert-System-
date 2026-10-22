"""
3D Interactive Visualizers for Multimodal Fall Detection System.
Provides Three.js WebGL 3D Human Pose Fall Simulation and 3D Smartphone IMU Cube.
"""

def get_3d_skeleton_html(initial_state="standing"):
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>3D Fall Digital Twin</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          background: #090d16;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          overflow: hidden;
          color: #fff;
          user-select: none;
        }
        #canvas-container {
          width: 100vw;
          height: 100vh;
          position: absolute;
          top: 0;
          left: 0;
        }
        .ui-overlay {
          position: absolute;
          top: 14px;
          left: 14px;
          right: 14px;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          pointer-events: none;
          z-index: 10;
        }
        .ui-panel {
          background: rgba(15, 23, 42, 0.85);
          backdrop-filter: blur(12px);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 12px;
          padding: 12px 16px;
          pointer-events: auto;
          box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        }
        .badge {
          display: inline-block;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 1px;
          text-transform: uppercase;
          background: rgba(59, 130, 246, 0.25);
          color: #60a5fa;
          padding: 3px 8px;
          border-radius: 20px;
          margin-bottom: 6px;
          border: 1px solid rgba(96, 165, 250, 0.3);
        }
        .title {
          font-size: 15px;
          font-weight: 800;
          color: #f8fafc;
        }
        .subtitle {
          font-size: 11px;
          color: #94a3b8;
          margin-top: 2px;
        }
        .btn-group {
          display: flex;
          gap: 6px;
          margin-top: 10px;
        }
        .btn {
          background: #1e293b;
          border: 1px solid rgba(255, 255, 255, 0.15);
          color: #cbd5e1;
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s;
        }
        .btn:hover {
          background: #334155;
          color: #fff;
          transform: translateY(-1px);
        }
        .btn.active {
          background: #2563eb;
          color: #fff;
          border-color: #3b82f6;
          box-shadow: 0 0 12px rgba(37, 99, 235, 0.6);
        }
        .btn-danger.active {
          background: #dc2626;
          border-color: #ef4444;
          box-shadow: 0 0 12px rgba(220, 38, 38, 0.7);
        }
        .telemetry-card {
          min-width: 170px;
          text-align: right;
        }
        .telemetry-val {
          font-size: 22px;
          font-weight: 900;
          font-family: monospace;
          color: #10b981;
        }
        .telemetry-val.crit {
          color: #ef4444;
          animation: blink 1s infinite;
        }
        @keyframes blink {
          50% { opacity: 0.6; }
        }
        .hint-text {
          position: absolute;
          bottom: 12px;
          left: 50%;
          transform: translateX(-50%);
          font-size: 11px;
          color: #64748b;
          background: rgba(15, 23, 42, 0.75);
          padding: 4px 12px;
          border-radius: 20px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          pointer-events: none;
        }
      </style>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    </head>
    <body>
      <div id="canvas-container"></div>

      <div class="ui-overlay">
        <div class="ui-panel">
          <div class="badge">3D Digital Twin</div>
          <div class="title">Biomechanical Fall Simulation</div>
          <div class="subtitle">17 Anatomical Keypoints & Floor Impact Surface</div>
          <div class="btn-group">
            <button class="btn active" id="btn-stand" onclick="setPose('stand')">🟢 Standing</button>
            <button class="btn" id="btn-stumble" onclick="setPose('stumble')">🟡 Stumble</button>
            <button class="btn btn-danger" id="btn-fall" onclick="setPose('fall')">🚨 Fall Impact</button>
            <button class="btn" id="btn-animate" onclick="toggleAnimation()">▶️ Animate Fall</button>
          </div>
        </div>

        <div class="ui-panel telemetry-card">
          <div class="badge" id="status-badge" style="background:rgba(16, 185, 129, 0.2); color:#34d399; border-color:#10b981;">SAFE</div>
          <div class="subtitle">Fall Severity</div>
          <div class="telemetry-val" id="sev-display">8.5%</div>
          <div class="subtitle" id="posture-state">Upright Posture</div>
        </div>
      </div>

      <div class="hint-text">🖱️ Drag to rotate 360° | Scroll to zoom | Right-click to pan</div>

      <script>
        // Setup Three.js Scene
        const container = document.getElementById('canvas-container');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0a0f1d);
        scene.fog = new THREE.FogExp2(0x0a0f1d, 0.035);

        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
        camera.position.set(0, 2.2, 5.2);

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.target.set(0, 1.0, 0);
        controls.maxPolarAngle = Math.PI / 2 + 0.05; // Don't go far below ground

        // Lights
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);

        const dirLight = new THREE.DirectionalLight(0x60a5fa, 1.2);
        dirLight.position.set(5, 8, 5);
        dirLight.castShadow = true;
        dirLight.shadow.mapSize.width = 1024;
        dirLight.shadow.mapSize.height = 1024;
        scene.add(dirLight);

        const pointLight = new THREE.PointLight(0x38bdf8, 1.5, 10);
        pointLight.position.set(-2, 3, 2);
        scene.add(pointLight);

        // Emergency Strobe Light (turned on when falling)
        const redStrobe = new THREE.PointLight(0xef4444, 0, 15);
        redStrobe.position.set(0, 2, 0);
        scene.add(redStrobe);

        // Grid & Floor
        const grid = new THREE.GridHelper(16, 24, 0x38bdf8, 0x1e293b);
        grid.position.y = 0;
        scene.add(grid);

        const floorGeo = new THREE.PlaneGeometry(30, 30);
        const floorMat = new THREE.MeshStandardMaterial({
          color: 0x070b14,
          roughness: 0.8,
          metalness: 0.2,
        });
        const floor = new THREE.Mesh(floorGeo, floorMat);
        floor.rotation.x = -Math.PI / 2;
        floor.receiveShadow = true;
        scene.add(floor);

        // Impact Target Ring
        const ringGeo = new THREE.RingGeometry(0.3, 0.45, 32);
        const ringMat = new THREE.MeshBasicMaterial({ color: 0xef4444, side: THREE.DoubleSide, transparent: true, opacity: 0 });
        const impactRing = new THREE.Mesh(ringGeo, ringMat);
        impactRing.rotation.x = -Math.PI / 2;
        impactRing.position.set(0, 0.02, 0);
        scene.add(impactRing);

        // Human Figure Model Group
        const humanGroup = new THREE.Group();
        scene.add(humanGroup);

        // Materials
        const jointMat = new THREE.MeshStandardMaterial({ color: 0x38bdf8, roughness: 0.3, metalness: 0.8, emissive: 0x0284c7, emissiveIntensity: 0.3 });
        const headMat = new THREE.MeshStandardMaterial({ color: 0x60a5fa, roughness: 0.2, metalness: 0.5 });
        const boneMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.4, metalness: 0.6 });
        const spineMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, roughness: 0.3, metalness: 0.7 });

        // Build Mannequin Parts
        const joints = {};
        const bones = [];

        function createJoint(name, radius, mat = jointMat) {
          const geo = new THREE.SphereGeometry(radius, 20, 20);
          const mesh = new THREE.Mesh(geo, mat);
          mesh.castShadow = true;
          humanGroup.add(mesh);
          joints[name] = mesh;
          return mesh;
        }

        function createBone(j1Name, j2Name, radius = 0.04, mat = boneMat) {
          const geo = new THREE.CylinderGeometry(radius, radius, 1, 16);
          const mesh = new THREE.Mesh(geo, mat);
          mesh.castShadow = true;
          humanGroup.add(mesh);
          bones.push({ mesh, j1: j1Name, j2: j2Name });
          return mesh;
        }

        // 17 COCO Keypoints
        createJoint('nose', 0.12, headMat);
        createJoint('left_shoulder', 0.07);
        createJoint('right_shoulder', 0.07);
        createJoint('left_elbow', 0.06);
        createJoint('right_elbow', 0.06);
        createJoint('left_wrist', 0.05);
        createJoint('right_wrist', 0.05);
        createJoint('left_hip', 0.08);
        createJoint('right_hip', 0.08);
        createJoint('left_knee', 0.07);
        createJoint('right_knee', 0.07);
        createJoint('left_ankle', 0.06);
        createJoint('right_ankle', 0.06);
        createJoint('chest', 0.10, spineMat);
        createJoint('pelvis', 0.09, spineMat);

        // Connections
        createBone('nose', 'chest', 0.05);
        createBone('chest', 'pelvis', 0.06, spineMat);
        createBone('chest', 'left_shoulder', 0.045);
        createBone('chest', 'right_shoulder', 0.045);
        createBone('left_shoulder', 'left_elbow', 0.04);
        createBone('left_elbow', 'left_wrist', 0.035);
        createBone('right_shoulder', 'right_elbow', 0.04);
        createBone('right_elbow', 'right_wrist', 0.035);
        createBone('pelvis', 'left_hip', 0.05);
        createBone('pelvis', 'right_hip', 0.05);
        createBone('left_hip', 'left_knee', 0.05);
        createBone('left_knee', 'left_ankle', 0.04);
        createBone('right_hip', 'right_knee', 0.05);
        createBone('right_knee', 'right_ankle', 0.04);

        // Predefined Pose Configurations
        const poses = {
          stand: {
            nose: [0, 1.75, 0],
            chest: [0, 1.45, 0],
            pelvis: [0, 1.05, 0],
            left_shoulder: [-0.26, 1.48, 0],
            right_shoulder: [0.26, 1.48, 0],
            left_elbow: [-0.34, 1.15, 0],
            right_elbow: [0.34, 1.15, 0],
            left_wrist: [-0.34, 0.85, 0],
            right_wrist: [0.34, 0.85, 0],
            left_hip: [-0.18, 1.02, 0],
            right_hip: [0.18, 1.02, 0],
            left_knee: [-0.19, 0.55, 0.02],
            right_knee: [0.19, 0.55, 0.02],
            left_ankle: [-0.19, 0.08, 0],
            right_ankle: [0.19, 0.08, 0],
            rot: [0, 0, 0],
            yOffset: 0,
            sev: 8.5,
            status: 'SAFE',
            color: '#10b981',
            desc: 'Upright Stable Posture'
          },
          stumble: {
            nose: [0.15, 1.40, 0.35],
            chest: [0.08, 1.18, 0.22],
            pelvis: [0, 0.85, 0],
            left_shoulder: [-0.24, 1.25, 0.28],
            right_shoulder: [0.30, 1.15, 0.15],
            left_elbow: [-0.38, 1.10, 0.45],
            right_elbow: [0.45, 0.95, 0.30],
            left_wrist: [-0.42, 0.95, 0.65],
            right_wrist: [0.55, 0.80, 0.50],
            left_hip: [-0.18, 0.84, 0.05],
            right_hip: [0.18, 0.84, -0.05],
            left_knee: [-0.22, 0.45, 0.30],
            right_knee: [0.20, 0.48, -0.15],
            left_ankle: [-0.24, 0.08, 0.45],
            right_ankle: [0.18, 0.08, -0.25],
            rot: [0.35, 0.15, -0.2],
            yOffset: 0,
            sev: 48.0,
            status: 'MILD RISK',
            color: '#f59e0b',
            desc: 'Unstable Gait / Stumble'
          },
          fall: {
            nose: [0.85, 0.20, 0.15],
            chest: [0.50, 0.18, 0.05],
            pelvis: [0.00, 0.16, 0.00],
            left_shoulder: [0.52, 0.22, -0.22],
            right_shoulder: [0.48, 0.14, 0.25],
            left_elbow: [0.65, 0.18, -0.38],
            right_elbow: [0.30, 0.12, 0.42],
            left_wrist: [0.75, 0.12, -0.45],
            right_wrist: [0.18, 0.08, 0.48],
            left_hip: [-0.02, 0.16, -0.18],
            right_hip: [0.02, 0.16, 0.18],
            left_knee: [-0.45, 0.14, -0.25],
            right_knee: [-0.48, 0.12, 0.22],
            left_ankle: [-0.85, 0.10, -0.28],
            right_ankle: [-0.90, 0.08, 0.20],
            rot: [0, 0, 0],
            yOffset: 0,
            sev: 94.2,
            status: 'CRITICAL FALL',
            color: '#ef4444',
            desc: 'Person Down / Prone on Floor'
          }
        };

        let currentPoseKey = 'stand';
        let targetPositions = JSON.parse(JSON.stringify(poses.stand));
        let isAnimating = false;
        let animProgress = 0;
        let animDir = 1;

        function updateBoneMeshes() {
          const v1 = new THREE.Vector3();
          const v2 = new THREE.Vector3();
          const mid = new THREE.Vector3();

          bones.forEach(b => {
            const j1 = joints[b.j1];
            const j2 = joints[b.j2];
            if (!j1 || !j2) return;

            j1.getWorldPosition(v1);
            j2.getWorldPosition(v2);

            const dist = v1.distanceTo(v2);
            b.mesh.scale.set(1, dist, 1);

            mid.addVectors(v1, v2).multiplyScalar(0.5);
            b.mesh.position.copy(mid);

            b.mesh.quaternion.setFromUnitVectors(
              new THREE.Vector3(0, 1, 0),
              v2.clone().sub(v1).normalize()
            );
          });
        }

        window.setPose = function(key) {
          isAnimating = false;
          currentPoseKey = key;
          const pose = poses[key];

          document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
          const btn = document.getElementById('btn-' + key);
          if (btn) btn.classList.add('active');

          const badge = document.getElementById('status-badge');
          badge.innerText = pose.status;
          badge.style.background = pose.color + '33';
          badge.style.color = pose.color;
          badge.style.borderColor = pose.color;

          const sevDisplay = document.getElementById('sev-display');
          sevDisplay.innerText = pose.sev.toFixed(1) + '%';
          sevDisplay.style.color = pose.color;
          if (pose.sev >= 75) {
            sevDisplay.classList.add('crit');
            impactRing.material.opacity = 0.85;
            redStrobe.intensity = 2.5;
          } else {
            sevDisplay.classList.remove('crit');
            impactRing.material.opacity = 0;
            redStrobe.intensity = 0;
          }

          document.getElementById('posture-state').innerText = pose.desc;
        };

        window.toggleAnimation = function() {
          isAnimating = !isAnimating;
          document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
          const btnAnim = document.getElementById('btn-animate');
          if (isAnimating) {
            btnAnim.classList.add('active');
            btnAnim.innerText = '⏸️ Pause';
          } else {
            btnAnim.innerText = '▶️ Animate Fall';
          }
        };

        // Render loop with smooth lerping
        function animate() {
          requestAnimationFrame(animate);

          // Handle sequence animation
          if (isAnimating) {
            animProgress += 0.012 * animDir;
            if (animProgress >= 1.0) {
              animProgress = 1.0;
              animDir = -1;
            } else if (animProgress <= 0.0) {
              animProgress = 0.0;
              animDir = 1;
            }

            // Lerp from stand (0) to fall (1)
            const pStand = poses.stand;
            const pFall = poses.fall;

            for (let name in pStand) {
              if (Array.isArray(pStand[name])) {
                const j = joints[name];
                if (j) {
                  j.position.x = THREE.MathUtils.lerp(pStand[name][0], pFall[name][0], animProgress);
                  j.position.y = THREE.MathUtils.lerp(pStand[name][1], pFall[name][1], animProgress);
                  j.position.z = THREE.MathUtils.lerp(pStand[name][2], pFall[name][2], animProgress);
                }
              }
            }

            const curSev = THREE.MathUtils.lerp(8.5, 94.2, animProgress);
            document.getElementById('sev-display').innerText = curSev.toFixed(1) + '%';
            if (curSev >= 75) {
              document.getElementById('status-badge').innerText = 'CRITICAL FALL';
              document.getElementById('status-badge').style.color = '#ef4444';
              document.getElementById('sev-display').style.color = '#ef4444';
              impactRing.material.opacity = 0.85 * animProgress;
              redStrobe.intensity = 2.5 * animProgress;
            } else {
              document.getElementById('status-badge').innerText = curSev > 35 ? 'MILD RISK' : 'SAFE';
              document.getElementById('status-badge').style.color = curSev > 35 ? '#f59e0b' : '#10b981';
              document.getElementById('sev-display').style.color = curSev > 35 ? '#f59e0b' : '#10b981';
              impactRing.material.opacity = 0;
              redStrobe.intensity = 0;
            }
          } else {
            // Lerp to selected target pose
            const target = poses[currentPoseKey];
            for (let name in target) {
              if (Array.isArray(target[name])) {
                const j = joints[name];
                if (j) {
                  j.position.x = THREE.MathUtils.lerp(j.position.x, target[name][0], 0.12);
                  j.position.y = THREE.MathUtils.lerp(j.position.y, target[name][1], 0.12);
                  j.position.z = THREE.MathUtils.lerp(j.position.z, target[name][2], 0.12);
                }
              }
            }
          }

          updateBoneMeshes();
          controls.update();
          renderer.render(scene, camera);
        }

        // Initialize with standing pose
        for (let name in poses.stand) {
          if (Array.isArray(poses.stand[name]) && joints[name]) {
            joints[name].position.set(poses.stand[name][0], poses.stand[name][1], poses.stand[name][2]);
          }
        }
        updateBoneMeshes();
        animate();

        window.addEventListener('resize', () => {
          camera.aspect = window.innerWidth / window.innerHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(window.innerWidth, window.innerHeight);
        });
      </script>
    </body>
    </html>
    """


def get_3d_phone_html():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>3D Smartphone IMU Cube</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          background: #090d16;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          overflow: hidden;
          color: #fff;
          user-select: none;
        }
        #canvas-container { width: 100vw; height: 100vh; position: absolute; top:0; left:0; }
        .ui-panel {
          position: absolute;
          top: 12px;
          left: 12px;
          background: rgba(15, 23, 42, 0.85);
          backdrop-filter: blur(10px);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 10px;
          padding: 10px 14px;
          z-index: 10;
        }
        .badge {
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 1px;
          background: rgba(16, 185, 129, 0.2);
          color: #34d399;
          padding: 2px 8px;
          border-radius: 20px;
          display: inline-block;
          margin-bottom: 4px;
        }
        .title { font-size: 14px; font-weight: 800; color: #f8fafc; }
        .controls-row {
          position: absolute;
          bottom: 14px;
          left: 14px;
          right: 14px;
          display: flex;
          justify-content: center;
          gap: 8px;
          z-index: 10;
        }
        .btn {
          background: #1e293b;
          border: 1px solid rgba(255, 255, 255, 0.2);
          color: #fff;
          padding: 6px 14px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
        }
        .btn:hover { background: #334155; }
        .btn.active { background: #2563eb; border-color: #60a5fa; }
      </style>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    </head>
    <body>
      <div id="canvas-container"></div>
      <div class="ui-panel">
        <div class="badge">9-Channel IMU Telemetry</div>
        <div class="title">3D Smartphone Orientation Cube</div>
        <div style="font-size:11px; color:#94a3b8; margin-top:2px;">Accel (XYZ) + Gravity (XYZ) + Gyro (XYZ)</div>
      </div>
      <div class="controls-row">
        <button class="btn active" onclick="setMode('idle')">📱 Upright Walking</button>
        <button class="btn" onclick="setMode('tilt')">⚡ Sharp Turn / Tilt</button>
        <button class="btn" onclick="setMode('fall')">🚨 Freefall & Impact Drop</button>
      </div>

      <script>
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x090d16);
        const camera = new THREE.PerspectiveCamera(40, window.innerWidth / window.innerHeight, 0.1, 100);
        camera.position.set(0, 1.2, 4);

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.shadowMap.enabled = true;
        document.getElementById('canvas-container').appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;

        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        scene.add(ambientLight);
        const dirLight = new THREE.DirectionalLight(0x38bdf8, 1.4);
        dirLight.position.set(4, 6, 4);
        scene.add(dirLight);

        // Floor Grid
        const grid = new THREE.GridHelper(10, 16, 0x38bdf8, 0x1e293b);
        grid.position.y = -1;
        scene.add(grid);

        // Smartphone Body (Chassis)
        const phoneGroup = new THREE.Group();
        scene.add(phoneGroup);

        const bodyGeo = new THREE.BoxGeometry(1.2, 2.4, 0.12);
        const bodyMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.2, metalness: 0.8 });
        const bodyMesh = new THREE.Mesh(bodyGeo, bodyMat);
        phoneGroup.add(bodyMesh);

        // Glass Screen
        const screenGeo = new THREE.PlaneGeometry(1.1, 2.2);
        const screenMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, roughness: 0.1, metalness: 0.9, emissive: 0x0369a1, emissiveIntensity: 0.4 });
        const screenMesh = new THREE.Mesh(screenGeo, screenMat);
        screenMesh.position.z = 0.065;
        phoneGroup.add(screenMesh);

        // Gimbal Orientation Rings (3 Axes)
        function createAxisRing(radius, color, rotAxis) {
          const ringGeo = new THREE.TorusGeometry(radius, 0.015, 16, 64);
          const ringMat = new THREE.MeshBasicMaterial({ color, opacity: 0.7, transparent: true });
          const ring = new THREE.Mesh(ringGeo, ringMat);
          if (rotAxis === 'x') ring.rotation.y = Math.PI / 2;
          if (rotAxis === 'z') ring.rotation.x = Math.PI / 2;
          phoneGroup.add(ring);
        }
        createAxisRing(1.6, 0xef4444, 'x'); // Pitch (Red)
        createAxisRing(1.65, 0x10b981, 'y'); // Yaw (Green)
        createAxisRing(1.7, 0x3b82f6, 'z'); // Roll (Blue)

        let targetRot = { x: 0, y: 0, z: 0 };
        let mode = 'idle';

        window.setMode = function(m) {
          mode = m;
          document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
          event.target.classList.add('active');
        };

        function animate() {
          requestAnimationFrame(animate);
          const t = Date.now() * 0.002;

          if (mode === 'idle') {
            targetRot.x = Math.sin(t * 2) * 0.15;
            targetRot.y = Math.cos(t) * 0.1;
            targetRot.z = Math.sin(t) * 0.05;
          } else if (mode === 'tilt') {
            targetRot.x = 0.6;
            targetRot.y = Math.sin(t * 3) * 0.4;
            targetRot.z = -0.7;
          } else if (mode === 'fall') {
            targetRot.x = 1.45;
            targetRot.y = 0.2;
            targetRot.z = 1.35;
          }

          phoneGroup.rotation.x = THREE.MathUtils.lerp(phoneGroup.rotation.x, targetRot.x, 0.1);
          phoneGroup.rotation.y = THREE.MathUtils.lerp(phoneGroup.rotation.y, targetRot.y, 0.1);
          phoneGroup.rotation.z = THREE.MathUtils.lerp(phoneGroup.rotation.z, targetRot.z, 0.1);

          controls.update();
          renderer.render(scene, camera);
        }
        animate();

        window.addEventListener('resize', () => {
          camera.aspect = window.innerWidth / window.innerHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(window.innerWidth, window.innerHeight);
        });
      </script>
    </body>
    </html>
    """
