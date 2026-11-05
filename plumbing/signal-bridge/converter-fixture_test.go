// SPDX-License-Identifier: AGPL-3.0-or-later
// Synthetic fixtures only. Uses the real ToMatrix direct-media path, no Signal I/O.
package msgconv

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/google/uuid"
	"google.golang.org/protobuf/proto"
	"maunium.net/go/mautrix/bridgev2"
	"maunium.net/go/mautrix/bridgev2/networkid"
	"maunium.net/go/mautrix/event"
	"maunium.net/go/mautrix/id"

	"go.mau.fi/mautrix-signal/pkg/signalid"
	"go.mau.fi/mautrix-signal/pkg/signalmeow"
	"go.mau.fi/mautrix-signal/pkg/signalmeow/protobuf/signalpb"
	"go.mau.fi/mautrix-signal/pkg/signalmeow/store"
)

type wizardFixtureMatrix struct { bridgev2.MatrixConnector }
func (wizardFixtureMatrix) GenerateContentURI(_ context.Context, mediaID networkid.MediaID) (id.ContentURIString, error) {
	return id.ContentURIString("mxc://fixture/" + base64.RawURLEncoding.EncodeToString(mediaID)), nil
}
type wizardFixtureIntent struct { bridgev2.MatrixAPI }

func wizardFixtureMessage() *signalpb.DataMessage {
	dm := &signalpb.DataMessage{Timestamp: proto.Uint64(1700000000123), Body: proto.String("Three photos")}
	for i, name := range []string{"red.png", "green.png", "blue.png"} {
		dm.Attachments = append(dm.Attachments, &signalpb.AttachmentPointer{
			AttachmentIdentifier: &signalpb.AttachmentPointer_CdnId{CdnId: uint64(i+1)},
			ContentType: proto.String("image/png"), FileName: proto.String(name),
			Width: proto.Uint32(640), Height: proto.Uint32(480), Size: proto.Uint32(7),
			Key: make([]byte, 64), Digest: make([]byte, 32),
		})
	}
	return dm
}

func TestWizardConverterFixture(t *testing.T) {
	candidate := os.Getenv("WIZARD_EXPECT_ALBUM") == "1"
	sender := uuid.MustParse("11111111-1111-4111-8111-111111111111")
	mc := NewMessageConverter(&bridgev2.Bridge{Matrix: wizardFixtureMatrix{}})
	mc.DirectMedia = true
	client := &signalmeow.Client{Store: &store.Device{}}
	convert := func(dm *signalpb.DataMessage, who uuid.UUID) *bridgev2.ConvertedMessage {
		return mc.ToMatrix(context.Background(), client, &bridgev2.Portal{}, who, wizardFixtureIntent{}, dm, nil)
	}
	dm := wizardFixtureMessage()
	cm := convert(dm, sender)
	wantParts := 4
	if candidate { wantParts = 3 }
	if len(cm.Parts) != wantParts { t.Fatalf("parts=%d want=%d", len(cm.Parts), wantParts) }
	var records []map[string]any
	for i, part := range cm.Parts {
		if part.ID != signalid.MakeMessagePartID(i) { t.Fatalf("mapping changed for part %d", i) }
		meta, ok := part.DBMetadata.(*signalid.MessageMetadata)
		if !ok || !meta.ContainsAttachments || meta.ViewOnce { t.Fatalf("bad mapping metadata: %+v", part.DBMetadata) }
		var content map[string]any
		data, err := json.Marshal(part.Content); if err != nil { t.Fatal(err) }
		if err = json.Unmarshal(data, &content); err != nil { t.Fatal(err) }
		for k, v := range part.Extra { content[k] = v }
		if candidate {
			group, ok := part.Extra["org.wizard.signal.album"].(map[string]any)
			if !ok || group["id"] != string(signalid.MakeMessageID(sender, dm.GetTimestamp())) || group["index"] != i || group["count"] != 3 { t.Fatalf("bad marker: %+v", group) }
			name := dm.Attachments[i].GetFileName()
			if i == 0 {
				if part.Content.Body != "Three photos" || part.Content.FileName != name { t.Fatal("caption or filename lost") }
			} else if part.Content.Body != name { t.Fatal("filename/order changed") }
		} else if part.Extra["org.wizard.signal.album"] != nil { t.Fatal("unpatched converter unexpectedly groups") }
		records = append(records, map[string]any{"type": "m.room.message", "event_id": []string{"$z-red", "$a-green", "$m-blue", "$caption"}[i], "sender": "@signal_fixture:test", "origin_server_ts": dm.GetTimestamp(), "content": content, "native_part_id": string(part.ID)})
	}
	if out := os.Getenv("WIZARD_FIXTURE_OUT"); out != "" {
		if err := os.MkdirAll(filepath.Dir(out), 0755); err != nil { t.Fatal(err) }
		data, err := json.MarshalIndent(records, "", "  "); if err != nil { t.Fatal(err) }
		if err = os.WriteFile(out, data, 0644); err != nil { t.Fatal(err) }
	}
	for _, tc := range []struct{name string; change func(*signalpb.DataMessage)}{
		{"single", func(d *signalpb.DataMessage){d.Attachments = d.Attachments[:1]}},
		{"mixed-video", func(d *signalpb.DataMessage){d.Attachments[1].ContentType = proto.String("video/mp4")}},
		{"mixed-file", func(d *signalpb.DataMessage){d.Attachments[1].ContentType = proto.String("application/pdf")}},
		{"bad-later-conversion", func(d *signalpb.DataMessage){d.Attachments[2].AttachmentIdentifier = nil}},
		{"view-once", func(d *signalpb.DataMessage){d.IsViewOnce = proto.Bool(true)}},
		{"payment", func(d *signalpb.DataMessage){d.Payment = &signalpb.DataMessage_Payment{}}},
	} {
		t.Run(tc.name, func(t *testing.T){
			d := wizardFixtureMessage(); tc.change(d)
			result := convert(d, sender)
			for _, part := range result.Parts { if part.Extra["org.wizard.signal.album"] != nil { t.Fatal("unsafe grouping") } }
		})
	}
	if candidate {
		// Signal's native identity is (sender, timestamp), not timestamp alone.
		other := convert(wizardFixtureMessage(), uuid.MustParse("22222222-2222-4222-8222-222222222222"))
		if cm.Parts[0].Extra["org.wizard.signal.album"].(map[string]any)["id"] == other.Parts[0].Extra["org.wizard.signal.album"].(map[string]any)["id"] { t.Fatal("independent native IDs collided") }
	}
	_ = event.MsgImage // keep upstream event type dependency explicit
}
