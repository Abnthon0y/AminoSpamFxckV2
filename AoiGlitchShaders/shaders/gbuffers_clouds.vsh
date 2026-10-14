#version 120
#define VERTEX_SHADER
/* AoiGlitch — gbuffers_clouds: vanilla clouds are disabled.
   1) shaders.properties: clouds = off   -> the game does not even submit them
   2) this program discards every fragment -> safety net if a loader, a mod or
      the video settings force clouds back on.                               */

void main() {
    gl_Position = ftransform();
}
